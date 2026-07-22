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
    "google_news_bd": "Google News中文",
    "kr36_ai": "36氪",
    "36kr_ai": "36氪",
    "ai_hot_feed": "AI热点",
    "cnbeta": "cnBeta",
    "ithome": "IT之家",
    "ifanr": "爱范儿",
    "tmtpost": "钛媒体",
    "qbitai": "量子位",
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


# ============ 字节 AI 曝光聚焦（软性倾斜，可配置） ============
# 字节系关键词的默认集合（config.display.bytedance_keywords 可覆盖）
BYTEDANCE_DEFAULT_KEYWORDS = [
    "字节", "字节跳动", "bytedance", "抖音", "douyin", "tiktok", "豆包", "doubao",
    "即梦", "jimeng", "剪映", "capcut", "火山引擎", "volcano", "coze", "扣子",
    "seedream", "seedance",
]

# 其他国内大厂分组（字节单独处理，故此处不含字节）
DOMESTIC_OTHER_GROUPS = {
    "百度": ["baidu", "ernie", "百度", "文心", "apollo", "萝卜快跑"],
    "腾讯": ["tencent", "hunyuan", "腾讯", "混元", "元宝"],
    "快手": ["kuaishou", "kling", "快手", "可灵"],
    "阿里": ["alibaba", "qwen", "阿里", "通义", "万相", "阿里妈妈"],
}


def get_display_config(config):
    return (config or {}).get("display", {}) or {}


def get_bytedance_keywords(config):
    d = get_display_config(config)
    kws = d.get("bytedance_keywords") or BYTEDANCE_DEFAULT_KEYWORDS
    return [str(k).lower() for k in kws]


def get_bytedance_only(config):
    """硬开关：True 时整个 pipeline 只处理字节系条目，其他公司条目一律不进入任何环节。"""
    return bool(get_display_config(config).get("bytedance_only", False))


def filter_bytedance_only(items, config):
    """当 bytedance_only 打开时，把资讯池收敛到仅字节系条目。"""
    return [it for it in items if is_bytedance_item(it, config)]


def is_bytedance_item(item, config):
    text = (item.get("title", "") + " " + (item.get("content") or item.get("description", "")))
    # 用带词边界的匹配（keyword_in_text 已在下面定义），避免 "ark" 命中 "market"、
    # "seed" 命中 "seeds"、"lark" 命中 "clark" 这类误召回。
    for kw in get_bytedance_keywords(config):
        if keyword_in_text(kw, text):
            return True
    return False


def count_bytedance(items, config):
    return sum(1 for it in items if is_bytedance_item(it, config))


def _domestic_other_group(item):
    t = (item.get("title", "") + " " + (item.get("content") or item.get("description", ""))).lower()
    for name, kws in DOMESTIC_OTHER_GROUPS.items():
        if any(w in t for w in kws):
            return name
    return None


def item_has_quality_info(item, biz):
    """其他公司纳入时的质量门槛：需为'必要产品/功能信息、鲜明完整观点、有价值生态信息'，
    且有足够信息量（描述不能太短），避免为凑数纳入信息量低的条目。"""
    title = item.get("title", "") or ""
    desc = (item.get("content") or item.get("description", "") or "")
    text = (title + " " + desc).lower()
    product_kw = ["发布", "推出", "上线", "更新", "升级", "功能", "产品", "平台", "api", "模型",
                  "model", "launch", "release", "update", "introduc", "unveil", "feature", "tool"]
    opinion_kw = list(biz.get("analysis_keywords", [])) + [
        "认为", "观点", "预测", "分析", "报告", "says", "forecast", "outlook", "analyst"]
    eco_kw = ["开源", "监管", "芯片", "合作", "融资", "收购", "投资", "生态", "基础设施",
              "partnership", "open source", "chip", "funding", "acquisition", "regulation",
              "infrastructure", "deal"]
    has_product = any(keyword_in_text(k, text) for k in product_kw)
    has_opinion = any(keyword_in_text(k, text) for k in opinion_kw)
    has_eco = any(keyword_in_text(k, text) for k in eco_kw)
    substantive = len(desc.strip()) >= 50
    return substantive and (has_product or has_opinion or has_eco)


def select_curated_with_focus(scored, config, biz, total=24, other_quota_each=2):
    """在已打分排序（降序）的 scored=[(score,item),...] 上做软性择优，逼近字节目标占比。

    护栏：
    - 开关关闭或池中字节条目 < bytedance_min_items 时返回 None（表示不做倾斜，走原逻辑）。
    - 字节名额 ≈ round(total * target_ratio)，从字节高分条目择优，不机械填满、以目标区间为上限。
    - 保留其他国内大厂（百度/腾讯/快手/阿里）每家保底配额，优先过质量门槛的条目。
    - 其余名额按原有打分在其他公司里择优，other_company_quality_only 开启时过质量门槛。
    返回选定的 [(score,item),...]（长度≈total），或 None。
    """
    display = get_display_config(config)

    # 硬开关：bytedance_only=True 时，直接返回字节池里按分数降序的前 N 条，
    # 不再回填任何非字节条目，不再做 32% 配比计算。若字节条目不足 total，就有多少给多少。
    if display.get("bytedance_only"):
        bd_only = [si for si in scored if is_bytedance_item(si[1], config)]
        bd_only.sort(key=lambda x: x[0], reverse=True)
        return bd_only[:total]

    if not display.get("bytedance_focus"):
        return None
    ratio = float(display.get("bytedance_target_ratio", 0.32))
    min_items = int(display.get("bytedance_min_items", 3))
    quality_only = bool(display.get("other_company_quality_only", True))

    bd = [si for si in scored if is_bytedance_item(si[1], config)]
    # 护栏：字节太少，退回正常逻辑，绝不硬凑
    if len(bd) < min_items:
        return None

    total = min(total, len(scored))
    bd_slots = min(len(bd), max(1, int(round(total * ratio))))

    selected = []
    ids = set()

    # 1) 字节高分择优（不超过目标名额，避免过度渲染）
    for si in bd[:bd_slots]:
        selected.append(si)
        ids.add(id(si[1]))

    others = [si for si in scored if id(si[1]) not in ids]

    # 2) 其他国内大厂保底配额（先取过质量门槛的高分条目，不足再放宽）
    quota_counts = {n: 0 for n in DOMESTIC_OTHER_GROUPS}
    for require_gate in (True, False):
        for si in others:
            if len(selected) >= total:
                break
            if id(si[1]) in ids:
                continue
            g = _domestic_other_group(si[1])
            if not g or quota_counts[g] >= other_quota_each:
                continue
            if require_gate and quality_only and not item_has_quality_info(si[1], biz):
                continue
            selected.append(si)
            ids.add(id(si[1]))
            quota_counts[g] += 1

    # 3) 其余名额：其他公司高分 + 质量门槛（门槛过严导致名额填不满时再放宽兜底）
    for require_gate in (True, False):
        for si in others:
            if len(selected) >= total:
                break
            if id(si[1]) in ids:
                continue
            if require_gate and quality_only and not item_has_quality_info(si[1], biz):
                continue
            selected.append(si)
            ids.add(id(si[1]))
        if len(selected) >= total:
            break

    selected.sort(key=lambda x: x[0], reverse=True)
    return selected


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


def prefilter_items(items, biz, limit=70, config=None):
    """按商业价值预打分，截取 top N 送入 AI，缩短输入、提高精选质量。

    额外保证国内大厂（百度/腾讯/快手/字节/阿里）的配额，避免被 OpenAI/英伟达等
    高分国际公司挤出候选集，导致页面偏科。

    另：若 display.bytedance_focus 开启且池中字节条目 >= 阈值，则额外确保候选集中
    字节条目充足（供 AI 在最终精选里达到目标占比）；字节太少时不做此倾斜。
    """
    scored = [(score_item(it, biz), it) for it in items]
    scored.sort(key=lambda x: x[0], reverse=True)
    ordered = [it for _, it in scored]
    top = ordered[:limit]

    # 国内大厂配额：每家至少保证 quota_each 条进入候选集（若原始池里有的话）
    domestic_groups = {
        "百度": ["baidu", "ernie", "百度", "文心", "apollo", "萝卜快跑"],
        "腾讯": ["tencent", "hunyuan", "腾讯", "混元", "元宝"],
        "快手": ["kuaishou", "kling", "快手", "可灵"],
        "字节": ["bytedance", "doubao", "字节", "豆包", "抖音", "即梦", "coze"],
        "阿里": ["alibaba", "qwen", "阿里", "通义", "万相", "阿里妈妈"],
    }
    quota_each = 3

    def group_of(it):
        t = (it.get("title", "") + " " + it.get("description", "")).lower()
        for name, kws in domestic_groups.items():
            if any(w in t for w in kws):
                return name
        return None

    top_keys = set(id(it) for it in top)
    counts = {name: 0 for name in domestic_groups}
    for it in top:
        g = group_of(it)
        if g:
            counts[g] += 1

    # 从未入选的高分项里，为配额不足的公司补位
    for it in ordered:
        if id(it) in top_keys:
            continue
        g = group_of(it)
        if g and counts[g] < quota_each:
            top.append(it)
            top_keys.add(id(it))
            counts[g] += 1

    # 字节聚焦：确保候选集中字节条目充足，供 AI 在最终精选里逼近目标占比。
    display = get_display_config(config)
    if display.get("bytedance_focus"):
        bd_all = [it for it in ordered if is_bytedance_item(it, config)]
        if len(bd_all) >= int(display.get("bytedance_min_items", 3)):
            ratio = float(display.get("bytedance_target_ratio", 0.32))
            max_curated = ((config or {}).get("ai", {}) or {}).get("max_curated_items", 18)
            want = min(len(bd_all), int(round(max_curated * ratio)) + 3)
            bd_in_top = sum(1 for it in top if is_bytedance_item(it, config))
            for it in bd_all:  # bd_all 已按分数降序（源自 ordered）
                if bd_in_top >= want:
                    break
                if id(it) in top_keys:
                    continue
                top.append(it)
                top_keys.add(id(it))
                bd_in_top += 1

    return top


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
    {"base": "某类技术能力底座的具体变化（谁把什么底座能力从 A 改成了 B）", "borrow": "对'拿商家预算做外部广告投放(外投)'的商业化团队(如美团商业化)有什么借鉴或可落地的动作"}
  ],
  "insights_intro": "一句话点题（40-70字）：换个视角，对像美团商业化这类'拿商家预算做外投'的团队来说，今天这些公司在'技术能力底座'上的改造，意味着未来外投的素材/投放/成本结构会怎么变。"
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

    # 字节聚焦：仅在开关开启且候选集中字节条目充足时，追加一层软性倾斜 + 概述客观性约束。
    display = get_display_config(config)
    focus_block = ""
    bytedance_only = bool(display.get("bytedance_only"))
    if bytedance_only:
        focus_block = (
            "\n## 【硬约束：仅字节系】\n"
            "11. 本次报道的读者只关心字节跳动全系 AI 商业化动态。上面这批候选资讯已由外部过滤器**收敛到只包含字节系条目**"
            "（字节跳动/抖音/TikTok/豆包/火山引擎/火山方舟/扣子Coze/即梦/剪映/巨量引擎/Seedance/Seedream/Trae 等）。\n"
            "12. items 只能围绕字节系资讯做筛选与中文摘要，**严禁选入或提及任何非字节公司的动态**（OpenAI/谷歌/Anthropic/微软/Meta/阿里/百度/腾讯/快手/英伟达/xAI 等非字节公司若被误传入，请忽略）。\n"
            "13. editorial_summary / overview（new_products/opinions/ecosystem）/ category_summaries / local_life_insights / insights_intro **全部只围绕字节系** AI 商业化做归因与结论，不要跨到非字节公司。\n"
            "14. 若候选资讯数量少于 " + str(max_curated) + " 条，就有多少写多少，宁缺毋滥，**严禁**用非字节内容或空话补位。\n"
        )
    elif display.get("bytedance_focus"):
        bd_count = count_bytedance(items, config)
        if bd_count >= int(display.get("bytedance_min_items", 3)):
            ratio = float(display.get("bytedance_target_ratio", 0.32))
            lo = int(round((ratio - 0.02) * 100))
            hi = int(round((ratio + 0.03) * 100))
            focus_block = (
                "\n## 字节跳动关注（本报读者为美团商业化管理层，字节系我方重点，务必自然、不过度渲染）\n"
                "11. 【字节适度突出，勿过度】本次原始资讯中字节跳动系相关内容充足。请在【大厂动向】【观点与深度】【生态动向】"
                "三个分类里都适当多选字节跳动系（字节/字节跳动/抖音/TikTok/豆包/即梦/剪映/火山引擎/Coze/扣子/Seedream/Seedance 等）"
                "中确有实质信息量的条目，使字节相关条目在最终精选里占比约 " + str(lo) + "%-" + str(hi) + "%（这是目标上限区间，不要机械凑满，更不要整份只讲字节）。"
                "其他公司（OpenAI/谷歌/阿里/百度/腾讯/快手等）合计仍应占约 60%-70%，纳入时优先'必要的产品/功能信息''观点鲜明且完整的观点''有价值的生态信息'，不要为凑数选信息量低的条目。\n"
                "12. 【概述必须客观、基于全量】editorial_summary 与 overview（new_products/opinions/ecosystem）必须基于上面列出的全部资讯客观归因，"
                "如实反映 AI 行业整体态势与多家公司动态；不得因字节条目多而在概述/三维结论里过度突出字节——分类精选可以向字节适度倾斜，但概述与结论要保持多公司客观均衡。\n"
            )

    intro_text = ("你是一位顶级 AI 行业分析师编辑，为「本地生活商业化外投团队」编写每日 AI 商业中文日报。\n"
                  "读者画像：广告销售人员，关注头部大厂/AI 公司的商业动作、产品能力、落地效果，以及对广告/营销/本地生活的启发。\n")
    if bytedance_only:
        intro_text = ("你是一位顶级 AI 行业分析师编辑，为「本地生活商业化外投团队」编写每日**字节系 AI 商业化**中文日报。\n"
                      "读者画像：广告销售人员，本次报道**只围绕字节跳动全系 AI 商业化动态**（字节跳动/抖音/TikTok/豆包/火山引擎/火山方舟/扣子Coze/即梦/剪映/巨量引擎/Seedance/Seedream/Trae 等），不涉及其他公司。\n"
                      "所有筛选、中文摘要、编辑概述、三维结论、外投洞察都只围绕字节系公司做归因。\n")

    prompt = intro_text + """
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
10. 【最后一块换视角，但不许凑数】insights_intro + local_life_insights 从"技术能力底座改造"视角切入：只有当天资讯里**确实出现**了会影响外投素材生产/定向投放/成本结构的底座级变化时，才提炼；能挖出几条写几条，最多 3 条，宁缺毋滥。当天若没有真正相关的内容，就把 local_life_insights 返回空数组 []、insights_intro 返回空字符串 ""，**绝不允许为了有这一块而硬写**。每条要写清 base=底座能力具体发生了什么变化、borrow=对"拿商家预算做外部广告投放(外投)"的商业化团队(如美团商业化)有什么可落地借鉴；borrow 必须与当天这条 base 强相关，不能是放之四海皆准的空话。
""" + focus_block + """
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
    candidates = prefilter_items(items, biz, limit=70, config=config)
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
            insights_intro = data.get("insights_intro", "")

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
            return editorial, overview, curated_items, category_summaries, local_life_insights, insights_intro
        except Exception as e:
            last_err = e
            print("  [WARN] AI curation attempt " + str(attempt) + " failed: " + str(e))

    print("  [ERROR] AI curation failed after retries: " + str(last_err))
    return None, None, None, None, None, None


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


# ============ 外投团队视角：内容驱动的洞察（规则模式） ============
def derive_local_life_insights(news_items):
    """基于当天实际入选的资讯，按主题命中才输出对应的'外投借鉴'。

    重要：这里不做任何硬凑。只有当天新闻确实出现某类'技术底座级变化'主题时，
    才产出对应那一条；一条都没命中就返回 ("", [])，让页面自动不显示该模块，
    避免"为了总结而总结"。（此为规则模式兜底；AI 模式由 Prompt 第 10 条约束同样逻辑。）
    """
    # 每个主题：命中关键词 -> 对应 {base, borrow}
    themes = [
        {
            "kw": ["视频", "vids", "video", "sora", "可灵", "kling", "即梦", "数字人", "数字分身", "avatar", "veo", "runway"],
            "base": "生成式视频底座升级：视频从'套模板'转向'自然语言直接生成 + 数字分身出镜'。",
            "borrow": "外投团队可把'AI 批量生成商家口播/带货素材'纳入投放链路，用素材数量与快速迭代摊薄单条获客成本，而非继续依赖人工拍摄。",
        },
        {
            "kw": ["降价", "成本", "便宜", "token", "cheaper", "pricing", "性价比", "开源模型", "低价", "价格"],
            "base": "模型底座更大更便宜：调用成本持续下探，'千商千面'的定制生成在成本上开始可行。",
            "borrow": "外投可从'一套素材投所有人'转向按商家、按人群定制创意与文案，用精细化投放提升 ROI。",
        },
        {
            "kw": ["广告", "advertis", "营销", "marketing", "投放", "ad business", "ads"],
            "base": "AI 广告/自动投放底座在推进，但全自动投放的效果与品牌安全仍受质疑。",
            "borrow": "外投当前宜'AI 提效 + 人工兜底'：AI 做素材生产与初筛，把预算分配与品牌把关留给人，替商家守住 ROI。",
        },
        {
            "kw": ["agent", "智能体", "自动化", "workflow", "copilot"],
            "base": "Agent/智能体底座成熟：从'单点问答'走向'能自己跑流程'的多步自动化。",
            "borrow": "外投可试点用 Agent 串起'选品-生成素材-建计划-看数据-调预算'的投放闭环，减少人工重复操作。",
        },
    ]
    text = " ".join(
        (it.get("title", "") + " " + it.get("explanation", "") + " " +
         (it.get("content") or it.get("description", "") or "") + " " +
         " ".join(it.get("analysis_points", []) or []))
        for it in news_items
    ).lower()

    hits = []
    for th in themes:
        if any(kw.lower() in text for kw in th["kw"]):
            hits.append({"base": th["base"], "borrow": th["borrow"]})
        if len(hits) >= 3:
            break

    if not hits:
        return "", []
    intro = ("换个视角：对像美团商业化这类'拿商家预算做外部广告投放(外投)'的团队来说，"
             "今天真正值得关注的，是下面这些公司在'技术能力底座'上的改造对外投素材、投放与成本结构的影响。")
    return intro, hits


# ============ 规则模式 fallback（无 API / AI 失败时） ============
def rule_based_curate(items, config):
    biz = config.get("business_focus", {})
    scored = [(score_item(it, biz), it) for it in items]
    scored.sort(key=lambda x: x[0], reverse=True)

    # 字节聚焦：若开关开启且池中字节条目 >= 阈值，走软性择优（逼近目标占比 + 保留其他大厂配额 + 质量门槛）；
    # 否则（含字节太少的护栏分支）返回 None，退回原有 top20 + 国内大厂保底配额逻辑。
    focus_selection = select_curated_with_focus(scored, config, biz, total=24, other_quota_each=2)

    if focus_selection is not None:
        top_items = focus_selection
    else:
        top_items = scored[:20]

        # 国内大厂配额：保证百度/腾讯/快手/字节/阿里在兜底模式下也不被挤出
        domestic_groups = {
            "百度": ["baidu", "ernie", "百度", "文心", "apollo", "萝卜快跑"],
            "腾讯": ["tencent", "hunyuan", "腾讯", "混元", "元宝"],
            "快手": ["kuaishou", "kling", "快手", "可灵"],
            "字节": ["bytedance", "doubao", "字节", "豆包", "抖音", "即梦"],
            "阿里": ["alibaba", "qwen", "阿里", "通义", "万相"],
        }

        def _group_of(it):
            t = (it.get("title", "") + " " + it.get("description", "")).lower()
            for name, kws in domestic_groups.items():
                if any(w in t for w in kws):
                    return name
            return None

        picked_keys = set(id(it) for _, it in top_items)
        counts = {name: 0 for name in domestic_groups}
        for _, it in top_items:
            g = _group_of(it)
            if g:
                counts[g] += 1
        for sc, it in scored:
            if id(it) in picked_keys:
                continue
            g = _group_of(it)
            if g and counts[g] < 2:
                top_items.append((sc, it))
                picked_keys.add(id(it))
                counts[g] += 1
        top_items.sort(key=lambda x: x[0], reverse=True)

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

    # 归因/概述的输入池：护栏要求 overview、外投洞察等"归因"必须基于全量检索到的信息客观归因，
    # 不得因字节倾斜而偏向字节。故当启用字节倾斜时，用全量（去重后、按分排序）资讯池做归因；
    # 未倾斜时沿用原逻辑（curated 子集≈高分全量，二者等价）。
    if focus_selection is not None:
        attribution_items = [it for _, it in scored]
    else:
        attribution_items = news_items

    # 整段编辑概述（规则模式：聚合高影响条目，尽量成段）
    if focus_selection is not None:
        # 客观归因：核心看点取自全量高分池，避免只讲字节
        high_titles = [it.get("title", "") for it in attribution_items[:8] if it.get("title")][:4]
    else:
        high_titles = [i["title"] for i in news_items if i.get("impact") == "high"][:4]
        if not high_titles:
            high_titles = [i["title"] for i in news_items][:4]
    editorial = ("今日共精选 " + str(len(news_items)) + " 条 AI 商业动态，其中高影响 "
                 + str(len([i for i in news_items if i.get('impact') == 'high'])) + " 条。"
                 + "核心看点集中在：" + "；".join(t[:30] for t in high_titles)
                 + "。头部大厂在产品、营收与生态合作上持续加码，建议重点关注其能力更新对广告/营销与本地生活场景的可迁移性。")

    # 三维概述（规则模式：按关键词粗分聚合，best-effort，基于全量池客观归因）
    overview = build_rule_overview(attribution_items, biz)

    insights_intro, local_life_insights = derive_local_life_insights(attribution_items)

    return editorial, overview, news_items, category_summaries, local_life_insights, insights_intro


def build_rule_overview(news_items, biz):
    """规则模式下尽力构造三维结论（内容有限，AI 模式会更好）。"""
    new_products, opinions, ecosystem = [], [], []
    product_kw = ["发布", "推出", "上线", "更新", "launch", "release", "update", "introduc", "unveil"]
    opinion_kw = ["认为", "观点", "预测", "分析", "报告", "report", "says", "forecast", "outlook", "analyst"]
    eco_kw = ["监管", "开源", "芯片", "合作", "生态", "基础设施", "regulation", "open source", "chip", "partnership", "infrastructure"]
    for it in news_items:
        t = (it.get("title", "") + " " + it.get("explanation", "") + " "
             + (it.get("content") or it.get("description", "") or "")).lower()
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


def load_weekly_insights():
    """汇总本周每日日报里已产出的'外投借鉴'洞察(local_life_insights)，按 base 去重，取前 4 条。

    周报的'外投团队借鉴'完全来自每日已提炼的洞察——每日本身就是内容驱动、没有相关内容就不写。
    因此若本周没有任何一天产出过相关洞察，周报也返回空，不做任何硬凑。
    """
    collected = []
    intro = ""
    today = datetime.now(timezone(timedelta(hours=8)))
    monday = today - timedelta(days=today.weekday())
    for i in range(7):
        day = monday + timedelta(days=i)
        fp = os.path.join(DAILY_DIR, day.strftime("%Y-%m-%d") + ".json")
        if os.path.exists(fp):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not intro and data.get("insights_intro"):
                    intro = data.get("insights_intro")
                for ins in data.get("local_life_insights", []) or []:
                    if isinstance(ins, dict) and ins.get("base"):
                        collected.append(ins)
            except Exception:
                pass
    # 按 base 前 16 字去重
    seen = set()
    unique = []
    for ins in collected:
        key = str(ins.get("base", ""))[:16]
        if key in seen:
            continue
        seen.add(key)
        unique.append(ins)
    if not unique:
        return "", []
    return intro, unique[:4]


def build_weekly_editorial(unique, has_insights=True):
    high = [i for i in unique if i.get("impact") == "high"]
    high_titles = [i.get("title", "") for i in high][:5] or [i.get("title", "") for i in unique][:5]
    text = ("本周共汇总 " + str(len(unique)) + " 条 AI 商业要闻，其中高影响 " + str(len(high)) + " 条。"
            + "本周主线包括：" + "；".join(t[:28] for t in high_titles if t)
            + "。整体看，头部大厂在产品能力与商业化上继续领跑，生态侧的合作、融资与基础设施投入同步升温。")
    if has_insights:
        text += ("对像美团商业化这类'拿商家预算做外部广告投放(外投)'的团队而言，本周值得沉淀的不是单条新闻，"
                 "而是这些公司在'技术能力底座'上的改造——它决定了未来外投的素材生产、定向投放与成本结构会怎么变，"
                 "具体借鉴见文末'外投团队的借鉴'。")
    return text


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

    # 【硬开关：仅字节系】开启后，先把整个池子过滤成只保留字节系条目，
    # 后续所有环节（curated / overview / editorial / local_life_insights / weekly）
    # 全部基于这个"仅字节"池，绝不用非字节内容补位。
    if get_bytedance_only(config):
        before = len(items)
        items = filter_bytedance_only(items, config)
        print("  [INFO] bytedance_only=True: pool " + str(before)
              + " -> " + str(len(items)) + " (仅字节系)")

    editorial = ""
    overview = {}
    news_items = None
    category_summaries = {}
    local_life_insights = []
    insights_intro = ""
    ai_success = False

    # 空池优雅兜底：不调 AI、不崩，直接给占位输出
    if not items:
        print("  [INFO] Empty pool after ByteDance filter — emit placeholder digest")
        news_items = []
        if get_bytedance_only(config):
            editorial = "今日暂无字节系 AI 商业化资讯入池（可能是抓取窗口内相关报道较少，或已被昨日日报去重）。稍后将持续跟进字节跳动/抖音/TikTok/豆包/火山引擎/扣子/即梦/剪映/巨量引擎等产品线的新动态。"
        else:
            editorial = "今日暂无可精选的资讯。"
        overview = {"new_products": [], "opinions": [], "ecosystem": []}
        category_summaries = {}
        local_life_insights = []
        insights_intro = ""
    elif os.environ.get("OPENAI_API_KEY"):
        print("  [INFO] AI mode enabled")
        editorial, overview, news_items, category_summaries, local_life_insights, insights_intro = curate_with_ai(items, config)
        ai_success = news_items is not None

    if news_items is None:
        print("  [INFO] Using rule-based mode")
        editorial, overview, news_items, category_summaries, local_life_insights, insights_intro = rule_based_curate(items, config)

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
        "insights_intro": insights_intro or "",
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

        weekly_intro, weekly_insights = load_weekly_insights()

        weekly_output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "week_range": week_start + "-" + week_end,
            "date_display": week_start + " - " + week_end,
            "editorial_summary": build_weekly_editorial(unique, has_insights=bool(weekly_insights)),
            "overview": build_rule_overview(unique, config.get("business_focus", {})),
            "local_life_insights": weekly_insights,
            "insights_intro": weekly_intro,
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
