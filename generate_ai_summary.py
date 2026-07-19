#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_ai_summary.py

使用 DeepSeek API 将 100+ 条原始资讯精选为深度中文日报。

本版本重点修复/升级：
1. 【全中文】AI 精选严格要求所有标题、说明、分析要点翻译为中文，不再出现整段英文。
2. 【去水字数】删除无意义的「涉及公司：X」罗列，以及每条都带「动作」字样的模板句；
   要点只保留：这是什么产品/功能、能力如何变化、对商家/广告主的价值或可做的动作。
3. 【整段概述 + 三维结论】editorial_summary 由一句话升级为整段概述；新增 overview：
   - 新产品功能：哪个公司有什么新功能、具体怎么实现
   - 网上观点：网上报道对进展有什么新观点、论据是什么
   - 行业生态：基于这些文章，行业生态目前是什么态势
4. 【健壮性】使用 response_format=json、失败重试、宽松 JSON 解析；只有 AI 真正成功
   才把 mode 标记为 "ai"，否则如实降级为规则模式，避免"挂着 AI 名义实为英文模板"。
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
    "google_news_cn": "Google News中文",
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

CATEGORY_ORDER = ["大厂动向", "初创动向", "生态动向", "观点与深度"]

# 用于渲染层与生成层共同过滤的"水字数/空话"要点特征
FILLER_POINT_PATTERNS = [
    "关注其对竞争格局与商业化节奏的影响",
    "头部公司动作，关注其对行业标准与广告营销场景的辐射",
    "资本与融资动向，关注新玩家的商业模式与落地场景",
    "行业观点/数据，可用于判断趋势与市场空间",
    "生态/政策/基础设施变化，关注对上下游与合规的影响",
]


def looks_english(text):
    """粗略判断一段文本是否基本是英文（中文字符占比过低）。"""
    if not text:
        return False
    zh = len(re.findall(r"[\u4e00-\u9fff]", text))
    letters = len(re.findall(r"[A-Za-z]", text))
    if letters >= 10 and zh <= letters * 0.15:
        return True
    return False


# ============ 去重：加载昨天的数据 ============
def load_yesterday_urls():
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


# ============ 打分（预筛选 + 规则兜底共用） ============
def keyword_in_text(keyword, text):
    if not keyword or not text:
        return False
    kw = keyword.lower().strip()
    txt = text.lower()
    if re.match(r"^[a-z0-9][a-z0-9 .\-\+]*$", kw):
        pattern = r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])"
        return re.search(pattern, txt) is not None
    return kw in txt


def score_item(item, biz):
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
    # 有正文/较长描述的加分（给 AI 更多"如何实现/论据"素材）
    desc = item.get("description", "") or ""
    if len(desc) > 120:
        score += 10
    return score


def prefilter_items(items, biz, limit=70):
    """按商业价值预打分，截取 top N 送入 AI，缩短输入、提高精选质量。"""
    scored = [(score_item(it, biz), it) for it in items]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in scored[:limit]]


# ============ DeepSeek AI 精选模式 ============
AI_JSON_SCHEMA_HINT = """返回一个 JSON 对象（纯 JSON，不要 markdown 代码块），字段如下：
{
  "editorial_summary": "整段编辑概述（一段话，150-260字）。用一段连贯的话串起今天最重要的 3-5 件事，要有观点和逻辑，禁止只写一句话敷衍。",
  "overview": {
    "new_products": ["新产品功能结论：哪个公司推出/更新了什么产品或功能，具体是怎么实现的（技术路径/交互方式/面向人群），40-80字", "（1-3条，没有则给空数组）"],
    "opinions": ["网上观点结论：网上报道或分析师对某公司进展/某趋势提出了什么新观点，其论据是什么（数据、事实、案例），40-80字", "（1-3条）"],
    "ecosystem": ["行业生态结论：基于这些文章，AI 行业生态目前呈现什么态势（竞争/合作/监管/基础设施/资本流向），40-80字", "（1-3条）"]
  },
  "category_summaries": {
    "大厂动向": "本分类 2-3 句话综述（提炼核心脉络与看点，不要罗列标题）",
    "初创动向": "本分类 2-3 句话综述",
    "生态动向": "本分类 2-3 句话综述",
    "观点与深度": "本分类 2-3 句话综述"
  },
  "items": [
    {
      "title": "中文标题（20-35字，简洁有力，必须是中文）",
      "explanation": "核心说明（这条讲什么 + 为什么重要，全中文，60-120字）",
      "analysis_points": [
        "要点1：这是什么产品/功能，从什么变成了什么（能力/体验的具体变化）",
        "要点2：对商家/广告主/本地生活意味着什么价值，或可以做什么具体动作"
      ],
      "category": "大厂动向 / 初创动向 / 生态动向 / 观点与深度",
      "type": "fact / opinion",
      "impact": "high / medium / low",
      "source": "来源媒体名",
      "url": "原文链接（从输入中原样保留）",
      "local_life_hint": "对本地生活/广告/营销的启发（不相关则空字符串）"
    }
  ],
  "local_life_insights": [
    "面向本地生活广告销售团队的可落地启发（结合当日资讯给出具体动作，如"可以…""建议…"）"
  ]
}"""


def build_ai_prompt(items, config, max_curated):
    items_text = ""
    for i, item in enumerate(items, 1):
        title = item.get("title", "").strip()
        desc = (item.get("content") or item.get("description", "")).strip()
        source = SOURCE_NAMES.get(item.get("source", ""), item.get("source", ""))
        url = item.get("url", "")
        line = str(i) + ". [" + source + "] " + title
        if desc:
            line += " | " + desc[:400]
        if url:
            line += " | URL: " + url
        items_text += line + "\n"

    biz = config.get("business_focus", {})
    top_companies = ", ".join(biz.get("top_companies", [])[:20])

    prompt = """你是一位顶级 AI 行业分析师编辑，为「本地生活商业化外投团队」编写每日 AI 商业中文日报。
读者画像：广告销售人员，关注头部大厂/AI 公司的商业动作、产品能力、落地效果，以及对广告/营销/本地生活的启发。

## 任务
从下面 """ + str(len(items)) + """ 条原始资讯中，精选 """ + str(max_curated) + """ 条最有商业价值的内容，并做深度中文解读。

## 输出格式
""" + AI_JSON_SCHEMA_HINT + """

## 强制要求（务必逐条遵守）
1. 【全中文】所有 title / explanation / analysis_points / overview / summaries 必须是中文。原文是英文的必须翻译成中文，绝不允许直接照抄整段英文。
2. 【要点有料】每条 analysis_points 给 2-3 条，聚焦：①这是什么产品/功能、能力从什么变成什么；②对商家/广告主/本地生活的价值或可做的动作。
3. 【禁止水字数】严禁输出以下几类空话：
   - 单纯罗列公司名（如"涉及公司：Google"）——若要提公司，必须结合它具体做了什么；
   - "关注其对竞争格局与商业化节奏的影响""头部公司动作，关注其对行业标准的辐射"这类万能句；
   - 每条都硬凑"动作"二字。真有动作就写清楚动作，没有就不写这一条。
4. 【概述成段】editorial_summary 必须是一整段有逻辑的话，不能是一句话。
5. 【三维结论】overview 的三个维度（new_products / opinions / ecosystem）尽量都给内容；某维度确实无料时给空数组，不要硬编。
6. 必须覆盖国内大厂（百度/腾讯/阿里/字节跳动豆包即梦/快手可灵/小红书），原始资讯中有相关内容必须入选。
7. 优先有具体数据（金额、增长率、用户数）的条目；同一事件只保留信息量最大的一条；不选纯代码/论文，聚焦商业价值。
8. 分类规则：大厂动向=""" + top_companies + """ 等头部公司产品/营收/战略；初创动向=AI 初创融资/新品/商业模式；生态动向=行业趋势/监管/开源/基础设施；观点与深度=行业报告/CEO 观点/市场预测。
9. 影响等级：high=头部公司重大动作/大额融资(>1亿美元)/行业拐点；medium=值得关注的趋势/中型融资/产品更新；low=一般信息流。

---
原始资讯：
""" + items_text
    return prompt


def _extract_json(text):
    """宽松解析：先直接 parse，失败则尝试截取到最后一个完整的 } 再 parse。"""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if "```" in text:
            text = text.rsplit("```", 1)[0]
        text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    # 尝试从第一个 { 到最后一个 } 之间截取
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass
    raise ValueError("无法解析为 JSON")


def curate_with_ai(items, config):
    """调用 DeepSeek，返回 (editorial, overview, items, category_summaries, local_life_insights) 或全 None。"""
    from openai import OpenAI

    ai_config = config.get("ai", {})
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", ai_config.get("base_url", "https://api.deepseek.com"))
    model = os.environ.get("AI_MODEL", ai_config.get("model", "deepseek-chat"))
    max_curated = ai_config.get("max_curated_items", 18)

    biz = config.get("business_focus", {})
    # 预筛选：把最有价值的 70 条送入，缩短输入、降低输出被截断的风险
    candidates = prefilter_items(items, biz, limit=70)
    prompt = build_ai_prompt(candidates, config, max_curated)

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=120.0)

    last_err = None
    for attempt in range(1, 3):
        try:
            print("  [INFO] Calling DeepSeek API (model: " + model + ", attempt " + str(attempt) + ")...")
            kwargs = dict(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=8000,
            )
            # DeepSeek 支持 json_object，强制返回合法 JSON
            try:
                resp = client.chat.completions.create(
                    response_format={"type": "json_object"}, **kwargs)
            except Exception as e_fmt:
                print("  [WARN] json_object 模式不可用，回退普通模式: " + str(e_fmt))
                resp = client.chat.completions.create(**kwargs)

            result_text = resp.choices[0].message.content.strip()
            data = _extract_json(result_text)

            editorial = data.get("editorial_summary", "")
            overview = data.get("overview", {}) or {}
            curated_items = data.get("items", []) or []
            category_summaries = data.get("category_summaries", {}) or {}
            local_life_insights = data.get("local_life_insights", []) or []

            # 质量校验：必须有条目，且标题基本是中文（否则视为失败）
            if not curated_items:
                raise ValueError("AI 返回 items 为空")
            english_titles = sum(1 for it in curated_items if looks_english(it.get("title", "")))
            if english_titles > len(curated_items) * 0.4:
                raise ValueError("AI 返回标题大量为英文，判定翻译失败")

            # 清洗每条要点里的空话
            for it in curated_items:
                it["analysis_points"] = clean_points(it.get("analysis_points", []))

            print("  [OK] AI curated " + str(len(curated_items)) + " items")
            print("  [OK] Editorial: " + editorial[:60])
            return editorial, overview, curated_items, category_summaries, local_life_insights
        except Exception as e:
            last_err = e
            print("  [WARN] AI curation attempt " + str(attempt) + " failed: " + str(e))

    print("  [ERROR] AI curation failed after retries: " + str(last_err))
    return None, None, None, None, None


def clean_points(points):
    """去掉空话/水字数要点，去重，最多保留 3 条。"""
    cleaned = []
    seen = set()
    for p in points or []:
        if not p or not str(p).strip():
            continue
        p = str(p).strip()
        # 去掉纯"涉及公司：xxx"罗列
        if re.match(r"^涉及公司[:：]", p) and "，" not in p.rstrip("。"):
            continue
        if any(fp in p for fp in FILLER_POINT_PATTERNS):
            continue
        # 去掉重复
        key = p[:20]
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(p)
    return cleaned[:3]


# ============ 规则模式 fallback（无 API / AI 失败时） ============
def rule_based_curate(items, config):
    biz = config.get("business_focus", {})
    scored = [(score_item(it, biz), it) for it in items]
    scored.sort(key=lambda x: x[0], reverse=True)
    top_items = scored[:20]

    news_items = []
    for score, item in top_items:
        title = item.get("title", "")
        desc = (item.get("content") or item.get("description", "") or "")
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

        # 说明：仅当描述比标题更有信息量时才用描述，否则用标题
        if desc and desc.strip()[:40].lower() != title.strip()[:40].lower() and len(desc) > len(title) + 10:
            explanation = desc[:150]
        else:
            explanation = title[:150]

        # 要点：只保留真正有内容的（规则模式不翻译英文，故只在有增量信息时给要点）
        analysis_points = []
        if desc and len(desc) > len(title) + 30 and not looks_english(desc):
            analysis_points.append(desc[:110])

        if any(keyword_in_text(kw, text) for kw in biz.get("local_life_keywords", [])):
            local_hint = "与本地生活/广告营销相关，可评估在投放、素材或商家侧的落地机会。"
        else:
            local_hint = ""

        news_items.append({
            "title": title,
            "explanation": explanation,
            "analysis_points": clean_points(analysis_points),
            "category": category,
            "type": "fact",
            "impact": impact,
            "source": source,
            "url": item.get("url", ""),
            "local_life_hint": local_hint,
        })

    # 分类综述
    cat_items = {}
    for it in news_items:
        cat_items.setdefault(it.get("category", "大厂动向"), []).append(it)
    category_summaries = {}
    for cat, its in cat_items.items():
        titles = "、".join([i.get("title", "")[:16] for i in its[:3] if i.get("title")])
        category_summaries[cat] = ("本期" + cat + "共 " + str(len(its)) + " 条，涵盖：" + titles + " 等。")

    # 整段编辑概述（规则模式：聚合高影响条目，尽量成段）
    high_titles = [i["title"] for i in news_items if i.get("impact") == "high"][:4]
    if not high_titles:
        high_titles = [i["title"] for i in news_items][:4]
    editorial = ("今日共精选 " + str(len(news_items)) + " 条 AI 商业动态，其中高影响 "
                 + str(len([i for i in news_items if i.get('impact') == 'high'])) + " 条。"
                 + "核心看点集中在：" + "；".join(t[:30] for t in high_titles)
                 + "。头部大厂在产品、营收与生态合作上持续加码，建议重点关注其能力更新对广告/营销与本地生活场景的可迁移性。")

    # 三维概述（规则模式：按关键词粗分聚合，best-effort）
    overview = build_rule_overview(news_items, biz)

    local_life_insights = [
        "关注头部大厂的 AI 产品更新，评估其能力变化能否复用到本地生活的投放与素材生成。",
        "梳理本期与广告/营销相关的动态，主动向重点商家同步可落地的 AI 营销玩法。",
        "结合融资与新产品动向，提前储备潜在的合作与外投资源，抢占先发窗口。",
    ]

    return editorial, overview, news_items, category_summaries, local_life_insights


def build_rule_overview(news_items, biz):
    """规则模式下尽力构造三维结论（内容有限，AI 模式会更好）。"""
    new_products, opinions, ecosystem = [], [], []
    product_kw = ["发布", "推出", "上线", "更新", "launch", "release", "update", "introduc", "unveil"]
    opinion_kw = ["认为", "观点", "预测", "分析", "报告", "report", "says", "forecast", "outlook", "analyst"]
    eco_kw = ["监管", "开源", "芯片", "合作", "生态", "基础设施", "regulation", "open source", "chip", "partnership", "infrastructure"]
    for it in news_items:
        t = (it.get("title", "") + " " + it.get("explanation", "")).lower()
        title = it.get("title", "")[:40]
        if len(new_products) < 3 and any(k in t for k in product_kw):
            new_products.append(title)
        elif len(opinions) < 3 and any(k in t for k in opinion_kw):
            opinions.append(title)
        elif len(ecosystem) < 3 and any(k in t for k in eco_kw):
            ecosystem.append(title)
    return {
        "new_products": new_products,
        "opinions": opinions,
        "ecosystem": ecosystem,
    }


# ============ 周报聚合 ============
def load_weekly_items():
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


def build_weekly_editorial(unique):
    high = [i for i in unique if i.get("impact") == "high"]
    high_titles = [i.get("title", "") for i in high][:5] or [i.get("title", "") for i in unique][:5]
    return ("本周共汇总 " + str(len(unique)) + " 条 AI 商业要闻，其中高影响 " + str(len(high)) + " 条。"
            + "本周主线包括：" + "；".join(t[:28] for t in high_titles if t)
            + "。整体看，头部大厂在产品能力与商业化上继续领跑，生态侧的合作、融资与基础设施投入同步升温，"
            + "建议围绕上述动态梳理对本地生活广告投放与商家服务的迁移机会。")


# ============ 主流程 ============
def main():
    config = load_config()
    raw = load_raw_news()
    items = raw.get("items", [])

    print("=" * 60)
    print("AI Daily Digest - Deep Analysis Mode")
    print("   Raw items: " + str(len(items)))
    print("=" * 60)

    items = deduplicate_from_yesterday(items)
    print("  [INFO] After dedup: " + str(len(items)) + " items")

    editorial = ""
    overview = {}
    news_items = None
    category_summaries = {}
    local_life_insights = []
    ai_success = False

    if os.environ.get("OPENAI_API_KEY"):
        print("  [INFO] AI mode enabled")
        editorial, overview, news_items, category_summaries, local_life_insights = curate_with_ai(items, config)
        ai_success = news_items is not None

    if news_items is None:
        print("  [INFO] Using rule-based mode")
        editorial, overview, news_items, category_summaries, local_life_insights = rule_based_curate(items, config)

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
        "overview": overview or {},
        "category_summaries": category_summaries or {},
        "local_life_insights": local_life_insights or [],
        "total_items": len(news_items),
        "high_count": len([i for i in news_items if i.get("impact") == "high"]),
        "category_counts": category_counts,
        "items": news_items,
        # 只有 AI 真正成功才标记为 ai，避免"挂 AI 名义实为英文模板"
        "mode": "ai" if ai_success else "rule",
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
            "editorial_summary": build_weekly_editorial(unique),
            "overview": build_rule_overview(unique, config.get("business_focus", {})),
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
    print("Done! Curated: " + str(len(news_items)) + " | High: " + str(output["high_count"])
          + " | Mode: " + output["mode"])
    print("=" * 60)


if __name__ == "__main__":
    main()
