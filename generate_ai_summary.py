#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_ai_summary.py

使用 DeepSeek API（兼容 OpenAI SDK）将抓取的 100+ 条原始资讯精选为 10-15 条
高质量 AI 商业日报。输出风格对标「AI日报沉淀」：

- 分类：大厂动向 / 初创动向 / 生态动向 / 观点与深度
- 每条：中文标题 + 一句话说明（是什么 + 为什么重要）
- 标注：fact / 观点 + 高影响 / 中影响
- 周报聚合：本周精选条目去重合并

无 API Key 时自动降级为规则模式。
"""
import json
import os
import re
from datetime import datetime, timezone, timedelta


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DAILY_DIR = os.path.join(DATA_DIR, "daily")


def load_config():
    config_path = os.path.join(BASE_DIR, "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_raw_news():
    with open(os.path.join(DATA_DIR, "raw_news.json"), "r", encoding="utf-8") as f:
        return json.load(f)


SOURCE_NAMES = {
    "google_news_ai": "Google News",
    "kr36_ai": "36氪",
    "36kr_ai": "36氪",
    "ai_hot_feed": "AI热点",
    "venturebeat": "VentureBeat",
    "theverge": "The Verge",
    "hacker_news": "Hacker News",
}


# ============ DeepSeek / OpenAI 精选模式 ============
def curate_with_ai(items, config):
    """
    调用 DeepSeek API，从原始资讯中精选 10-15 条，
    按「AI日报沉淀」格式输出结构化 JSON。
    """
    from openai import OpenAI

    ai_config = config.get("ai", {})
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", ai_config.get("base_url", "https://api.deepseek.com"))
    model = os.environ.get("AI_MODEL", ai_config.get("model", "deepseek-chat"))
    max_curated = ai_config.get("max_curated_items", 15)

    client = OpenAI(api_key=api_key, base_url=base_url)

    # 准备输入：所有条目的标题 + 描述 + 来源 + URL
    items_text = ""
    for i, item in enumerate(items[:120], 1):
        title = item.get("title", "").strip()
        desc = item.get("description", "").strip()
        source = SOURCE_NAMES.get(item.get("source", ""), item.get("source", ""))
        url = item.get("url", "")
        line = str(i) + ". [" + source + "] " + title
        if desc:
            line += " | " + desc[:150]
        if url:
            line += " | URL: " + url
        items_text += line + "\n"

    biz = config.get("business_focus", {})
    top_companies = ", ".join(biz.get("top_companies", [])[:15])
    local_keywords = ", ".join(biz.get("local_life_keywords", [])[:8])

    prompt = """你是一位面向「本地生活商业化外投团队」的 AI 行业分析师编辑。
你的读者是销售人员，他们关注：
1. 头部互联网大厂和 AI 公司（""" + top_companies + """）的商业动作：产品发布、营收、融资、战略合作、落地效果
2. AI 如何改变广告、营销、本地生活（""" + local_keywords + """）等商业场景
3. 行业分析、财报数据、市场趋势

现在请从以下 """ + str(len(items[:120])) + """ 条原始资讯中，精选出最重要的 """ + str(max_curated) + """ 条（不超过 """ + str(max_curated) + """ 条），按以下规则输出：

## 分类规则（4个分类）：
- **大厂动向**：头部大公司（OpenAI/Google/Meta/Microsoft/Apple/Amazon/字节/百度/阿里/腾讯/Nvidia等）的商业动作
- **初创动向**：AI 初创公司（Anthropic/Mistral/Perplexity/Cohere 等）的融资、产品、合作
- **生态动向**：行业整体趋势、监管政策、开源社区、基础设施、芯片供应链等
- **观点与深度**：行业分析报告、财报解读、专家观点、市场预测

## 每条输出格式：
- title: 20-30字中文标题（简洁有力，一眼看懂）
- summary: 1-2句话说明"是什么 + 为什么重要"（50-100字）
- category: 上述4个分类之一
- type: "fact" 或 "opinion"（事实类 vs 观点类）
- impact: "high" 或 "medium"（高影响=头部公司重大动作/大额融资/行业拐点；中影响=值得关注）
- source: 来源媒体名
- url: 原文链接
- local_life_hint: 如果与本地生活/广告/营销相关，用一句话说明启发；否则为空字符串

## 精选原则：
1. 优先选择大厂重大商业动作（发布、营收、融资>5亿美元、战略合作）
2. 优先选择有具体数据的条目（金额、增长率、用户数）
3. 去重：同一事件只保留信息量最大的一条
4. 英文内容必须翻译为中文
5. 不要选纯技术/代码/论文类内容，聚焦商业价值
6. 每个分类至少 2 条，大厂动向占比最高

## 输出：
纯 JSON 数组，不要 markdown 代码块，不要额外说明。

---
原始资讯列表：
""" + items_text

    try:
        print("  [INFO] Calling DeepSeek API (model: " + model + ")...")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=6000,
        )
        result_text = response.choices[0].message.content.strip()

        # 清理可能的 markdown 代码块
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[1]
            if "```" in result_text:
                result_text = result_text.rsplit("```", 1)[0]
        result_text = result_text.strip()

        curated = json.loads(result_text)
        print("  [OK] AI curated " + str(len(curated)) + " items")

        # 标准化输出
        news_items = []
        for item in curated:
            news_items.append({
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "category": item.get("category", "大厂动向"),
                "type": item.get("type", "fact"),
                "impact": item.get("impact", "medium"),
                "source": item.get("source", ""),
                "url": item.get("url", ""),
                "local_life_hint": item.get("local_life_hint", ""),
            })
        return news_items

    except Exception as e:
        print("  [WARN] AI curation failed: " + str(e))
        print("  [INFO] Falling back to rule-based mode")
        return None


# ============ 规则模式 fallback ============
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


def rule_based_curate(items, config):
    """规则模式：按商业价值评分排序，取 top 15。"""
    biz = config.get("business_focus", {})

    scored = []
    for item in items:
        text = content_text(item)
        score = 30
        if any(keyword_in_text(c, text) for c in biz.get("top_companies", [])):
            score += 25
        commercial_hits = sum(1 for kw in biz.get("commercial_keywords", []) if keyword_in_text(kw, text))
        score += min(commercial_hits * 12, 30)
        analysis_hits = sum(1 for kw in biz.get("analysis_keywords", []) if keyword_in_text(kw, text))
        score += min(analysis_hits * 18, 36)
        if any(keyword_in_text(kw, text) for kw in biz.get("local_life_keywords", [])):
            score += 25
        if re.search(r"\$[\d,.]+|[\d,.]+\s*(亿|万)|billion|million|[\d.]+%", text.lower()):
            score += 10
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_items = scored[:15]

    news_items = []
    for score, item in top_items:
        title = item.get("title", "")
        desc = item.get("description", "") or ""
        source = SOURCE_NAMES.get(item.get("source", ""), item.get("source", ""))

        # 简单分类
        text = content_text(item).lower()
        if any(keyword_in_text(kw, text) for kw in ["融资", "收购", "ipo", "funding", "acquisition", "raises"]):
            category = "初创动向"
        elif any(keyword_in_text(kw, text) for kw in biz.get("analysis_keywords", [])):
            category = "观点与深度"
        elif any(keyword_in_text(kw, text) for kw in ["开源", "监管", "政策", "芯片", "chip", "regulation", "open source"]):
            category = "生态动向"
        else:
            category = "大厂动向"

        impact = "high" if score >= 70 else "medium"
        summary = desc[:200] if desc else title

        news_items.append({
            "title": title,
            "summary": summary,
            "category": category,
            "type": "fact",
            "impact": impact,
            "source": source,
            "url": item.get("url", ""),
            "local_life_hint": "",
        })

    return news_items


# ============ 周报聚合 ============
def load_weekly_items():
    """读取 data/daily/ 本周（周一至今）所有 json，合并精选条目。"""
    weekly = []
    today = datetime.now(timezone(timedelta(hours=8)))
    monday = today - timedelta(days=today.weekday())
    for i in range(7):
        day = monday + timedelta(days=i)
        fp = os.path.join(DAILY_DIR, day.strftime("%Y-%m-%d") + ".json")
        if os.path.exists(fp):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    weekly.extend(data.get("items", []))
            except Exception:
                pass
    return weekly


def deduplicate_items(items):
    """去重：按 url 或 title 去重。"""
    seen = set()
    unique = []
    for it in items:
        key = it.get("url") or it.get("title", "")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(it)
    return unique


# ============ 主流程 ============
def main():
    config = load_config()
    raw = load_raw_news()
    items = raw.get("items", [])

    print("=" * 60)
    print("AI Daily Digest - Curator Mode")
    print("   Raw items: " + str(len(items)))
    print("=" * 60)

    news_items = None

    # 优先使用 AI 精选模式
    if os.environ.get("OPENAI_API_KEY"):
        print("  [INFO] AI mode enabled (DeepSeek/OpenAI)")
        news_items = curate_with_ai(items, config)

    # AI 失败或无 Key 时降级
    if news_items is None:
        print("  [INFO] Using rule-based curation")
        news_items = rule_based_curate(items, config)

    # 构建输出
    beijing = timezone(timedelta(hours=8))
    now_bj = datetime.now(beijing)
    today_str = now_bj.strftime("%Y-%m-%d")

    # 按分类分组统计
    category_counts = {}
    for item in news_items:
        cat = item.get("category", "大厂动向")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date_display": now_bj.strftime("%Y年%m月%d日"),
        "date_short": today_str,
        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now_bj.weekday()],
        "total_items": len(news_items),
        "high_count": len([i for i in news_items if i.get("impact") == "high"]),
        "category_counts": category_counts,
        "items": news_items,
        "mode": "ai" if os.environ.get("OPENAI_API_KEY") else "rule",
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(DAILY_DIR, exist_ok=True)

    with open(os.path.join(DATA_DIR, "news_items.json"), "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    with open(os.path.join(DAILY_DIR, today_str + ".json"), "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 周报聚合
    weekly_items = load_weekly_items()
    if weekly_items:
        unique = deduplicate_items(weekly_items)
        # 按 impact 排序：high 在前
        unique.sort(key=lambda x: (0 if x.get("impact") == "high" else 1))

        week_start = (now_bj - timedelta(days=now_bj.weekday())).strftime("%m.%d")
        week_end = now_bj.strftime("%m.%d")

        weekly_category_counts = {}
        for item in unique:
            cat = item.get("category", "大厂动向")
            weekly_category_counts[cat] = weekly_category_counts.get(cat, 0) + 1

        weekly_output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "week_range": week_start + "-" + week_end,
            "date_display": week_start + " - " + week_end,
            "total_items": len(unique),
            "high_count": len([i for i in unique if i.get("impact") == "high"]),
            "category_counts": weekly_category_counts,
            "items": unique,
            "mode": output.get("mode", "rule"),
        }
        with open(os.path.join(DATA_DIR, "weekly_items.json"), "w", encoding="utf-8") as f:
            json.dump(weekly_output, f, ensure_ascii=False, indent=2)
        print("  [OK] Weekly aggregated: " + str(len(unique)) + " unique items")

    print()
    print("=" * 60)
    print("Done! Curated: " + str(len(news_items)) + " items"
          + " | High: " + str(output["high_count"])
          + " | Mode: " + output["mode"])
    for cat, count in sorted(category_counts.items()):
        print("   - " + cat + ": " + str(count))
    print("   Saved: data/news_items.json + data/daily/" + today_str + ".json")
    print("=" * 60)


if __name__ == "__main__":
    main()
