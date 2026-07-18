#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_ai_summary.py

使用 DeepSeek API 将 100+ 条原始资讯精选为 15-20 条深度日报。
对标「AI日报沉淀」文档：

- 每日编辑一句话总结（editorial_summary）
- 分类：大厂动向 / 初创动向 / 生态动向 / 观点与深度
- 每条：标题 + 核心说明 + 2-3 条深度分析子要点
- 影响等级：高影响(红) / 中影响(黄) / 信息流(灰)
- 类型：fact / opinion
- 去重：排除昨天已出现的内容
- 周报：一周精选聚合
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
    "techcrunch_ai": "TechCrunch",
    "the_rundown_ai": "The Rundown",
    "tldr_ai": "TLDR AI",
    "latent_space": "Latent Space",
    "one_useful_thing": "One Useful Thing",
    "a16z_ai": "A16Z",
    "product_hunt": "Product Hunt",
    "hacker_news": "Hacker News",
}


# ============ 去重：加载昨天的数据 ============
def load_yesterday_urls():
    """加载昨天的日报数据，用于去重。"""
    beijing = timezone(timedelta(hours=8))
    yesterday = datetime.now(beijing) - timedelta(days=1)
    yesterday_file = os.path.join(DAILY_DIR, yesterday.strftime("%Y-%m-%d") + ".json")
    urls = set()
    titles = set()
    if os.path.exists(yesterday_file):
        try:
            with open(yesterday_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("items", []):
                    if item.get("url"):
                        urls.add(item["url"])
                    if item.get("title"):
                        titles.add(item["title"][:20])
        except Exception:
            pass
    return urls, titles


def deduplicate_from_yesterday(items):
    """移除昨天已经出现过的条目。"""
    yesterday_urls, yesterday_titles = load_yesterday_urls()
    if not yesterday_urls and not yesterday_titles:
        return items

    filtered = []
    for item in items:
        url = item.get("url", "")
        title = item.get("title", "")[:20]
        if url in yesterday_urls:
            continue
        if title and title in yesterday_titles:
            continue
        filtered.append(item)

    removed = len(items) - len(filtered)
    if removed > 0:
        print("  [INFO] Removed " + str(removed) + " items (already in yesterday's digest)")
    return filtered


# ============ DeepSeek AI 精选模式 ============
def curate_with_ai(items, config):
    """
    调用 DeepSeek API，精选 15-20 条，每条含深度分析子要点。
    """
    from openai import OpenAI

    ai_config = config.get("ai", {})
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", ai_config.get("base_url", "https://api.deepseek.com"))
    model = os.environ.get("AI_MODEL", ai_config.get("model", "deepseek-chat"))
    max_curated = ai_config.get("max_curated_items", 20)

    client = OpenAI(api_key=api_key, base_url=base_url)

    # 构造输入
    items_text = ""
    for i, item in enumerate(items[:150], 1):
        title = item.get("title", "").strip()
        desc = item.get("description", "").strip()
        source = SOURCE_NAMES.get(item.get("source", ""), item.get("source", ""))
        url = item.get("url", "")
        line = str(i) + ". [" + source + "] " + title
        if desc:
            line += " | " + desc[:200]
        if url:
            line += " | URL: " + url
        items_text += line + "\n"

    biz = config.get("business_focus", {})
    top_companies = ", ".join(biz.get("top_companies", [])[:20])

    prompt = """你是一位顶级 AI 行业分析师编辑，为「本地生活商业化外投团队」编写每日 AI 商业日报。

读者画像：广告销售人员，关注头部大厂和 AI 公司的商业动作、落地效果、以及对广告/营销/本地生活的启发。

## 任务

从以下 """ + str(len(items[:150])) + """ 条原始资讯中，精选 """ + str(max_curated) + """ 条最有价值的内容。

## 输出要求

返回一个 JSON 对象，格式如下：
{
  "editorial_summary": "今日一句话编辑总结（提炼今天最核心的趋势/事件，20-40字）",
  "items": [
    {
      "title": "中文标题（20-35字，简洁有力）",
      "explanation": "核心说明（这条讲什么+为什么重要，60-120字）",
      "analysis_points": [
        "深度分析要点1（解读商业意义/竞争格局/对行业的影响，30-60字）",
        "深度分析要点2（延伸思考/对本地生活广告的启发，30-60字）"
      ],
      "category": "大厂动向 / 初创动向 / 生态动向 / 观点与深度",
      "type": "fact / opinion",
      "impact": "high / medium / low",
      "source": "来源媒体名",
      "url": "原文链接",
      "local_life_hint": "对本地生活/广告/营销的启发（如不相关则为空字符串）"
    }
  ]
}

## 分类规则
- **大厂动向**：""" + top_companies + """ 等头部公司的产品发布、营收、战略
- **初创动向**：AI 初创公司融资、新产品、商业模式
- **生态动向**：行业趋势、监管政策、开源、基础设施、开发者工具
- **观点与深度**：行业报告、CEO 观点、市场预测、深度分析

## 影响等级
- **high**（红色）：头部公司重大动作 / 大额融资(>1亿美元) / 行业拐点
- **medium**（黄色）：值得关注的趋势 / 中型融资 / 产品更新
- **low**（灰色）：一般信息流 / 小更新

## 精选原则
1. 每个分类至少 3 条，大厂动向占比最高
2. 优先有具体数据的条目（金额、增长率、用户数）
3. 同一事件只保留信息量最大的一条
4. 英文内容必须翻译为中文
5. 每条的 analysis_points 必须有 2-3 条，体现深度
6. 不选纯技术/代码/论文，聚焦商业价值
7. editorial_summary 要有观点，不是简单罗列

## 输出
纯 JSON，不要 markdown 代码块。

---
原始资讯：
""" + items_text

    try:
        print("  [INFO] Calling DeepSeek API (model: " + model + ")...")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=8000,
        )
        result_text = response.choices[0].message.content.strip()

        # 清理 markdown 代码块
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[1]
            if "```" in result_text:
                result_text = result_text.rsplit("```", 1)[0]
        result_text = result_text.strip()

        data = json.loads(result_text)
        editorial = data.get("editorial_summary", "")
        curated_items = data.get("items", [])
        print("  [OK] AI curated " + str(len(curated_items)) + " items")
        print("  [OK] Editorial: " + editorial)
        return editorial, curated_items

    except Exception as e:
        print("  [WARN] AI curation failed: " + str(e))
        return None, None


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


def rule_based_curate(items, config):
    """规则模式降级。"""
    biz = config.get("business_focus", {})
    scored = []
    for item in items:
        text = (item.get("title", "") + " " + item.get("description", "")).strip()
        score = 30
        if any(keyword_in_text(c, text) for c in biz.get("top_companies", [])):
            score += 25
        commercial_hits = sum(1 for kw in biz.get("commercial_keywords", []) if keyword_in_text(kw, text))
        score += min(commercial_hits * 10, 30)
        analysis_hits = sum(1 for kw in biz.get("analysis_keywords", []) if keyword_in_text(kw, text))
        score += min(analysis_hits * 15, 30)
        if any(keyword_in_text(kw, text) for kw in biz.get("local_life_keywords", [])):
            score += 20
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_items = scored[:20]

    editorial = "今日 AI 行业多条重要商业动态，头部公司持续发力。"
    news_items = []
    for score, item in top_items:
        title = item.get("title", "")
        desc = item.get("description", "") or ""
        source = SOURCE_NAMES.get(item.get("source", ""), item.get("source", ""))
        text = (title + " " + desc).lower()

        if any(keyword_in_text(kw, text) for kw in ["融资", "收购", "funding", "acquisition"]):
            category = "初创动向"
        elif any(keyword_in_text(kw, text) for kw in biz.get("analysis_keywords", [])):
            category = "观点与深度"
        elif any(keyword_in_text(kw, text) for kw in ["开源", "监管", "芯片", "regulation", "open source"]):
            category = "生态动向"
        else:
            category = "大厂动向"

        impact = "high" if score >= 75 else ("medium" if score >= 55 else "low")
        explanation = desc[:150] if desc else "关注 AI 行业最新商业动态。"

        news_items.append({
            "title": title,
            "explanation": explanation,
            "analysis_points": ["关注该动态对行业格局的影响", "思考对广告和营销场景的启发"],
            "category": category,
            "type": "fact",
            "impact": impact,
            "source": source,
            "url": item.get("url", ""),
            "local_life_hint": "",
        })

    return editorial, news_items


# ============ 周报聚合 ============
def load_weekly_items():
    """加载本周所有日报数据。"""
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


# ============ 主流程 ============
def main():
    config = load_config()
    raw = load_raw_news()
    items = raw.get("items", [])

    print("=" * 60)
    print("AI Daily Digest - Deep Analysis Mode")
    print("   Raw items: " + str(len(items)))
    print("=" * 60)

    # 去重：排除昨天的
    items = deduplicate_from_yesterday(items)
    print("  [INFO] After dedup: " + str(len(items)) + " items")

    editorial = ""
    news_items = None

    if os.environ.get("OPENAI_API_KEY"):
        print("  [INFO] AI mode enabled")
        editorial, news_items = curate_with_ai(items, config)

    if news_items is None:
        print("  [INFO] Using rule-based mode")
        editorial, news_items = rule_based_curate(items, config)

    # 输出
    beijing = timezone(timedelta(hours=8))
    now_bj = datetime.now(beijing)
    today_str = now_bj.strftime("%Y-%m-%d")

    category_counts = {}
    for item in news_items:
        cat = item.get("category", "大厂动向")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date_display": now_bj.strftime("%Y年%m月%d日"),
        "date_short": today_str,
        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now_bj.weekday()],
        "editorial_summary": editorial,
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

    # 周报
    weekly_items = load_weekly_items()
    if weekly_items:
        seen = set()
        unique = []
        for it in weekly_items:
            key = it.get("url") or it.get("title", "")
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(it)
        unique.sort(key=lambda x: (0 if x.get("impact") == "high" else 1))

        week_start = (now_bj - timedelta(days=now_bj.weekday())).strftime("%m.%d")
        week_end = now_bj.strftime("%m.%d")

        weekly_output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "week_range": week_start + "-" + week_end,
            "date_display": week_start + " - " + week_end,
            "editorial_summary": "本周 AI 行业精选要闻汇总",
            "total_items": len(unique),
            "high_count": len([i for i in unique if i.get("impact") == "high"]),
            "items": unique,
            "mode": output.get("mode", "rule"),
        }
        with open(os.path.join(DATA_DIR, "weekly_items.json"), "w", encoding="utf-8") as f:
            json.dump(weekly_output, f, ensure_ascii=False, indent=2)
        print("  [OK] Weekly: " + str(len(unique)) + " items")

    print()
    print("=" * 60)
    print("Done! Curated: " + str(len(news_items)) + " | High: " + str(output["high_count"]))
    print("   Editorial: " + editorial)
    print("=" * 60)


if __name__ == "__main__":
    main()
