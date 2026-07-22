#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_multi_source.py - 多源 AI 商业资讯抓取

信源（8个）：
- Google News AI Business（核心）
- 36Kr AI
- AI HOT Feed
- VentureBeat AI
- The Verge AI
- TechCrunch AI（新增）
- The Rundown AI（新增）
- Hacker News
"""
import json
import os
import re
import time
import html as html_lib
from datetime import datetime, timezone
from urllib.parse import quote_plus

import requests
import feedparser
from bs4 import BeautifulSoup


def load_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    # 把 display.bytedance_keywords 里的字节全系产品词合并进公司别名列表，
    # 让 cnbeta / tmtpost / qbitai / jiqizhixin 这些"按公司过滤"的中文源
    # 也能捕获火山引擎/扣子/即梦/剪映/巨量引擎等字节产品相关稿件。
    try:
        bd_kws = (config.get("display", {}) or {}).get("bytedance_keywords", []) or []
        seen_lower = {c.lower() for c in TOP_COMPANY_ALIASES}
        for kw in bd_kws:
            if not kw:
                continue
            k = str(kw).strip()
            if k and k.lower() not in seen_lower:
                TOP_COMPANY_ALIASES.append(k)
                seen_lower.add(k.lower())
    except Exception:
        pass
    return config


HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
}


# ============ 公司名匹配 ============
TOP_COMPANY_ALIASES = [
    "OpenAI", "ChatGPT", "Sam Altman",
    "Google", "Alphabet", "Gemini", "DeepMind",
    "Meta", "Instagram", "WhatsApp", "Llama", "Facebook",
    "Microsoft", "Copilot", "Azure",
    "Apple",
    "Amazon", "AWS",
    "Anthropic", "Claude",
    "ByteDance", "TikTok", "Doubao",
    "Baidu", "Ernie",
    "Alibaba", "Qwen",
    "Tencent",
    "Nvidia",
    "xAI", "Grok",
    "Mistral", "Cohere", "Perplexity", "Midjourney",
    "Stability AI", "Adobe", "Salesforce",
    "Runway", "ElevenLabs", "Suno", "Cursor",
    "Vercel", "Cloudflare",
]


def keyword_in_text(keyword, text):
    if not keyword or not text:
        return False
    kw = keyword.lower().strip()
    txt = text.lower()
    if re.match(r"^[a-z0-9][a-z0-9 .\-\+]*$", kw):
        pattern = r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])"
        return re.search(pattern, txt) is not None
    return kw in txt


def content_text(item):
    return (item.get("title", "") + " " + item.get("description", "")).strip()


def mentions_top_company(item):
    text = content_text(item)
    return any(keyword_in_text(kw, text) for kw in TOP_COMPANY_ALIASES)


_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]+",
    flags=re.UNICODE,
)


def strip_emoji(text):
    if not text:
        return text
    return _EMOJI_RE.sub("", text).strip()


def clean_summary(raw):
    if not raw:
        return ""
    txt = re.sub(r"<[^>]+>", " ", raw)
    txt = html_lib.unescape(txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


# ============ 正文补抓（给 AI 更多"如何实现/论据"素材） ============
def enrich_with_article_body(items, limit=40, timeout=8):
    """
    对描述较薄且有真实链接的条目，best-effort 抓取正文前几段，写入 item['content']。
    - 跳过 Google News 跳转链接（无法直接提取正文）
    - 带超时与总量上限，任何失败都静默跳过，绝不阻塞主流程。
    """
    enriched = 0
    for it in items:
        if enriched >= limit:
            break
        url = it.get("url", "") or ""
        desc = it.get("description", "") or ""
        if not url or url.startswith("http") is False:
            continue
        if "news.google.com" in url:  # 跳转页，抓不到真实正文
            continue
        if len(desc) >= 200:  # 已经比较充实
            continue
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
            if resp.status_code != 200 or not resp.text:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
                tag.decompose()
            paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
            paras = [p for p in paras if len(p) > 60]
            body = " ".join(paras[:6]).strip()
            if len(body) > max(len(desc), 120):
                it["content"] = body[:1500]
                enriched += 1
            time.sleep(0.2)
        except Exception:
            continue
    print("  [OK] Enriched " + str(enriched) + " items with article body")
    return items


# ============ Google News ============
def fetch_google_news_ai(config):
    print("[Google News AI] start...")
    results = []
    src = config["sources"].get("google_news_ai", {})
    queries = src.get("queries", [])
    base_url = src.get("base_url", "https://news.google.com/rss/search")
    hl = src.get("hl", "en-US")
    gl = src.get("gl", "US")
    ceid = src.get("ceid", "US:en")
    when = src.get("when", "2d")
    max_per_query = src.get("max_items_per_query", 10)

    seen = set()
    for query in queries:
        q = query + " when:" + when if when else query
        feed_url = base_url + "?q=" + quote_plus(q) + "&hl=" + hl + "&gl=" + gl + "&ceid=" + ceid
        try:
            feed = feedparser.parse(feed_url)
            count = 0
            for entry in feed.entries:
                if count >= max_per_query:
                    break
                title = entry.get("title", "").strip()
                publisher = ""
                m = re.search(r"\s-\s([^-]+)$", title)
                if m:
                    publisher = m.group(1).strip()
                    title = title[:m.start()].strip()
                link = entry.get("link", "").strip()
                summary = clean_summary(entry.get("summary", ""))
                if not title or len(title) < 8:
                    continue
                item = {
                    "source": "google_news_ai",
                    "title": title,
                    "description": summary[:500],
                    "url": link,
                    "publisher": publisher,
                    "published": entry.get("published", ""),
                    "fetch_time": datetime.now(timezone.utc).isoformat(),
                }
                if not mentions_top_company(item):
                    continue
                key = link or title
                if key in seen:
                    continue
                seen.add(key)
                results.append(item)
                count += 1
            time.sleep(0.3)
        except Exception as e:
            print("  [WARN] Google News query failed: " + str(e))
    print("  [OK] Google News AI: " + str(len(results)) + " items")
    return results


# ============ Google News 通用查询源 ============
def fetch_google_news_query(config, source_key, source_label):
    """通用 Google News RSS 查询源：按 config 里的 queries + locale 抓取。
    - google_news_cn：英文 locale，覆盖国内大厂有英文报道的宏观新闻。
    - google_news_bd：中文 locale + 中文产品名，覆盖火山/扣子/即梦/剪映/巨量等
      国内 B 端字节产品（英文 locale 对这些词返回 0，中文 locale 稳定出数）。
    查询词本身即过滤条件，不再叠加 mentions_top_company，避免误杀中文垂类稿。
    """
    src = config["sources"].get(source_key, {})
    print("[" + source_label + "] start...")
    results = []
    seen = set()
    base_url = src.get("base_url", "https://news.google.com/rss/search")
    hl = src.get("hl", "zh-CN")
    gl = src.get("gl", "CN")
    ceid = src.get("ceid", "CN:zh-Hans")
    when = src.get("when", "7d")
    max_per_query = src.get("max_items_per_query", 8)
    for query in src.get("queries", []):
        q = query + " when:" + when if when else query
        feed_url = (base_url + "?q=" + quote_plus(q)
                    + "&hl=" + hl + "&gl=" + gl + "&ceid=" + ceid)
        try:
            feed = feedparser.parse(feed_url)
            count = 0
            for entry in feed.entries:
                if count >= max_per_query:
                    break
                title = entry.get("title", "").strip()
                m = re.search(r"\s-\s([^-]+)$", title)
                if m:
                    title = title[:m.start()].strip()
                link = entry.get("link", "").strip()
                if not title or len(title) < 5:
                    continue
                key = link or title
                if key in seen:
                    continue
                seen.add(key)
                results.append({
                    "source": source_key,
                    "title": title,
                    "description": clean_summary(entry.get("summary", ""))[:500],
                    "url": link,
                    "published": entry.get("published", ""),
                    "fetch_time": datetime.now(timezone.utc).isoformat(),
                })
                count += 1
            time.sleep(0.3)
        except Exception as e:
            print("  [WARN] " + source_label + " query failed: " + str(e))
    print("  [OK] " + source_label + ": " + str(len(results)) + " items")
    return results


# ============ RSS 通用 ============
def fetch_rss_generic(source_key, source_name, feed_url, max_items, company_filter=False):
    print("[" + source_name + "] start...")
    results = []
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:max_items * 3]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = clean_summary(entry.get("summary", ""))
            if not title or len(title) < 5:
                continue
            item = {
                "source": source_key,
                "title": title,
                "description": summary[:500],
                "author": entry.get("author", ""),
                "published": entry.get("published", entry.get("updated", "")),
                "url": link,
                "fetch_time": datetime.now(timezone.utc).isoformat(),
            }
            if company_filter and not mentions_top_company(item):
                continue
            results.append(item)
            if len(results) >= max_items:
                break
    except Exception as e:
        print("  [WARN] " + source_name + " failed: " + str(e))
    print("  [OK] " + source_name + ": " + str(len(results)) + " items")
    return results


# ============ 36Kr AI ============
def fetch_36kr_ai(config):
    print("[36Kr AI] start...")
    results = []
    src = config["sources"].get("kr36_ai", {})
    max_items = src.get("max_items", 25)
    url = src.get("url", "https://36kr.com/information/AI/")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        anchors = soup.select('a.article-item-title, a[class*="title"], div.article-item a')
        seen = set()
        for a in anchors:
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if not title or len(title) < 5:
                continue
            if href and not href.startswith("http"):
                href = "https://36kr.com" + href
            if not href or href in seen:
                continue
            seen.add(href)
            results.append({
                "source": "36kr_ai",
                "title": title,
                "description": "",
                "url": href,
                "published": "",
                "fetch_time": datetime.now(timezone.utc).isoformat(),
            })
            if len(results) >= max_items:
                break
    except Exception as e:
        print("  [WARN] 36Kr web failed: " + str(e))
    if len(results) < 3:
        rss_url = src.get("rss_url", "https://36kr.com/feed/AI")
        try:
            feed = feedparser.parse(rss_url)
            seen = set(r["url"] for r in results)
            for entry in feed.entries[:max_items]:
                link = entry.get("link", "")
                if not link or link in seen:
                    continue
                seen.add(link)
                results.append({
                    "source": "36kr_ai",
                    "title": entry.get("title", ""),
                    "description": clean_summary(entry.get("summary", ""))[:300],
                    "url": link,
                    "published": entry.get("published", ""),
                    "fetch_time": datetime.now(timezone.utc).isoformat(),
                })
                if len(results) >= max_items:
                    break
        except Exception as e:
            print("  [WARN] 36Kr RSS failed: " + str(e))
    print("  [OK] 36Kr AI: " + str(len(results)) + " articles")
    return results


# ============ Hacker News ============
def fetch_hacker_news(config):
    print("[Hacker News] start...")
    results = []
    hn = config["sources"].get("hacker_news", {})
    api_url = hn.get("api_url", "https://hacker-news.firebaseio.com/v0")
    max_items = hn.get("max_items", 10)
    min_score = hn.get("min_score", 120)
    try:
        resp = requests.get(api_url + "/topstories.json", timeout=15)
        resp.raise_for_status()
        story_ids = resp.json()[:200]
        for story_id in story_ids:
            if len(results) >= max_items:
                break
            try:
                sr = requests.get(api_url + "/item/" + str(story_id) + ".json", timeout=10)
                story = sr.json()
                if not story or story.get("type") != "story":
                    continue
                score = story.get("score", 0)
                if score < min_score:
                    continue
                title = story.get("title", "")
                item = {
                    "source": "hacker_news",
                    "title": title,
                    "description": "",
                    "url": story.get("url", "https://news.ycombinator.com/item?id=" + str(story_id)),
                    "hn_url": "https://news.ycombinator.com/item?id=" + str(story_id),
                    "score": score,
                    "comments": story.get("descendants", 0),
                    "published": "",
                    "fetch_time": datetime.now(timezone.utc).isoformat(),
                }
                if not mentions_top_company(item):
                    continue
                results.append(item)
                time.sleep(0.05)
            except Exception:
                continue
    except Exception as e:
        print("  [WARN] Hacker News failed: " + str(e))
    print("  [OK] Hacker News: " + str(len(results)) + " posts")
    return results


# ============ 主流程 ============
def main():
    config = load_config()
    print("=" * 60)
    print("AI News Multi-Source Fetch")
    print("   Time: " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    print("=" * 60)

    all_items = []

    # Google News
    if config["sources"].get("google_news_ai", {}).get("enabled"):
        all_items.extend(fetch_google_news_ai(config))

    # Google News CN (国内大厂，英文 locale)
    cn_src = config["sources"].get("google_news_cn", {})
    if cn_src.get("enabled"):
        all_items.extend(fetch_google_news_query(config, "google_news_cn", "Google News CN"))

    # Google News 字节全系产品（中文 locale + 中文产品名，主力覆盖火山/扣子/即梦/剪映/巨量）
    bd_src = config["sources"].get("google_news_bd", {})
    if bd_src.get("enabled"):
        all_items.extend(fetch_google_news_query(config, "google_news_bd", "Google News 字节全系"))

    # 36Kr
    if config["sources"].get("kr36_ai", {}).get("enabled"):
        all_items.extend(fetch_36kr_ai(config))

    # AI HOT Feed
    src = config["sources"].get("ai_hot_feed", {})
    if src.get("enabled"):
        all_items.extend(fetch_rss_generic("ai_hot_feed", "AI HOT Feed",
                                            src.get("feed_url", ""), src.get("max_items", 25)))

    # cnBeta（中文科技，稳定高产，按公司过滤）
    src = config["sources"].get("cnbeta", {})
    if src.get("enabled"):
        all_items.extend(fetch_rss_generic("cnbeta", "cnBeta",
                                            src.get("feed_url", ""), src.get("max_items", 30),
                                            company_filter=True))

    # IT之家（中文科技资讯，feed 饱满，按公司/字节产品词过滤）
    src = config["sources"].get("ithome", {})
    if src.get("enabled"):
        all_items.extend(fetch_rss_generic("ithome", "IT之家 ithome",
                                            src.get("feed_url", ""), src.get("max_items", 30),
                                            company_filter=True))

    # 爱范儿 ifanr（中文科技/消费产品，按公司/字节产品词过滤）
    src = config["sources"].get("ifanr", {})
    if src.get("enabled"):
        all_items.extend(fetch_rss_generic("ifanr", "爱范儿 ifanr",
                                            src.get("feed_url", ""), src.get("max_items", 20),
                                            company_filter=True))

    # 钛媒体（默认禁用：GitHub 海外网络返回 0 条；保留配置以便需要时启用）
    src = config["sources"].get("tmtpost", {})
    if src.get("enabled"):
        all_items.extend(fetch_rss_generic("tmtpost", "TMTPost 钛媒体",
                                            src.get("feed_url", ""), src.get("max_items", 15),
                                            company_filter=True))

    # 量子位 QbitAI（默认禁用：GitHub 海外网络返回 0 条；同类内容由 google_news_bd 覆盖）
    src = config["sources"].get("qbitai", {})
    if src.get("enabled"):
        all_items.extend(fetch_rss_generic("qbitai", "量子位 QbitAI",
                                            src.get("feed_url", ""), src.get("max_items", 25),
                                            company_filter=True))

    # VentureBeat
    src = config["sources"].get("venturebeat", {})
    if src.get("enabled"):
        all_items.extend(fetch_rss_generic("venturebeat", "VentureBeat AI",
                                            src.get("feed_url", ""), src.get("max_items", 20),
                                            company_filter=True))

    # The Verge
    src = config["sources"].get("theverge", {})
    if src.get("enabled"):
        all_items.extend(fetch_rss_generic("theverge", "The Verge AI",
                                            src.get("feed_url", ""), src.get("max_items", 20),
                                            company_filter=True))

    # TechCrunch AI
    src = config["sources"].get("techcrunch_ai", {})
    if src.get("enabled"):
        all_items.extend(fetch_rss_generic("techcrunch_ai", "TechCrunch AI",
                                            src.get("feed_url", ""), src.get("max_items", 20)))

    # The Rundown AI
    src = config["sources"].get("the_rundown_ai", {})
    if src.get("enabled"):
        all_items.extend(fetch_rss_generic("the_rundown_ai", "The Rundown AI",
                                            src.get("feed_url", ""), src.get("max_items", 15)))

    # TLDR AI
    src = config["sources"].get("tldr_ai", {})
    if src.get("enabled"):
        all_items.extend(fetch_rss_generic("tldr_ai", "TLDR AI",
                                            src.get("feed_url", ""), src.get("max_items", 15)))

    # Latent Space
    src = config["sources"].get("latent_space", {})
    if src.get("enabled"):
        all_items.extend(fetch_rss_generic("latent_space", "Latent Space",
                                            src.get("feed_url", ""), src.get("max_items", 10)))

    # One Useful Thing
    src = config["sources"].get("one_useful_thing", {})
    if src.get("enabled"):
        all_items.extend(fetch_rss_generic("one_useful_thing", "One Useful Thing",
                                            src.get("feed_url", ""), src.get("max_items", 8)))

    # A16Z AI
    src = config["sources"].get("a16z_ai", {})
    if src.get("enabled"):
        all_items.extend(fetch_rss_generic("a16z_ai", "A16Z AI",
                                            src.get("feed_url", ""), src.get("max_items", 10)))

    # Product Hunt
    src = config["sources"].get("product_hunt", {})
    if src.get("enabled"):
        all_items.extend(fetch_rss_generic("product_hunt", "Product Hunt",
                                            src.get("feed_url", ""), src.get("max_items", 10)))

    # Hacker News
    if config["sources"].get("hacker_news", {}).get("enabled"):
        all_items.extend(fetch_hacker_news(config))

    # 去重
    seen = set()
    unique_items = []
    for it in all_items:
        it["title"] = strip_emoji(it.get("title", ""))
        it["description"] = strip_emoji(it.get("description", ""))
        key = it.get("url") or it.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        unique_items.append(it)

    sources_summary = {}
    for it in unique_items:
        s = it["source"]
        sources_summary[s] = sources_summary.get(s, 0) + 1

    # 正文补抓（best-effort，给 AI 更多素材）
    enrich_cfg = config.get("enrich", {})
    if enrich_cfg.get("enabled", True):
        print("[Enrich] fetching article bodies (best-effort)...")
        enrich_with_article_body(
            unique_items,
            limit=enrich_cfg.get("limit", 40),
            timeout=enrich_cfg.get("timeout", 8),
        )

    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    output = {
        "fetch_time": datetime.now(timezone.utc).isoformat(),
        "total_items": len(unique_items),
        "sources_summary": sources_summary,
        "items": unique_items,
    }

    with open(os.path.join(data_dir, "raw_news.json"), "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 60)
    print("Fetch complete! Total: " + str(len(unique_items)))
    for source, count in sorted(sources_summary.items(), key=lambda x: x[1], reverse=True):
        print("   - " + source + ": " + str(count))

    # 源健康度告警：配置为 enabled 但本次返回 0 条的源
    # 部分源的配置键与 item 里的 source 标签不一致，这里做别名映射
    source_tag_alias = {"kr36_ai": "36kr_ai"}
    enabled_sources = [k for k, v in config.get("sources", {}).items()
                       if isinstance(v, dict) and v.get("enabled")]
    empty_sources = [s for s in enabled_sources
                     if sources_summary.get(source_tag_alias.get(s, s), 0) == 0]
    if empty_sources:
        print("-" * 60)
        print("[WARN] 以下已启用的源本次返回 0 条（可能被限流/失效，需关注）：")
        for s in empty_sources:
            print("   ! " + s)

    # 国内大厂覆盖度检查
    domestic = {"百度": ["baidu", "ernie", "百度", "文心"],
                "腾讯": ["tencent", "hunyuan", "腾讯", "混元"],
                "快手": ["kuaishou", "kling", "快手", "可灵"]}
    dom_hits = {k: 0 for k in domestic}
    for it in unique_items:
        t = (it.get("title", "") + " " + it.get("description", "")).lower()
        for k, kws in domestic.items():
            if any(w in t for w in kws):
                dom_hits[k] += 1
    print("-" * 60)
    print("[国内大厂覆盖度] " + "  ".join(k + "=" + str(v) for k, v in dom_hits.items()))
    for k, v in dom_hits.items():
        if v == 0:
            print("   ! [WARN] 本次未抓到 " + k + " 相关资讯")
    print("=" * 60)


if __name__ == "__main__":
    main()
