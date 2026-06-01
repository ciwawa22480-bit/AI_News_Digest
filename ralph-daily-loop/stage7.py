#!/usr/bin/env python3
"""Goal 7: Merge + dedup + signal level for Day 5.

Note: 01-05 source files missing for this run; merging only 00-newsletter and 06-hn-consensus.
"""
import json
import re
import warnings
from difflib import SequenceMatcher
from pathlib import Path

DATA_DIR = Path("/data/userdata/daily-report/data")

# Source priority (higher = preferred when dedup conflict)
source_priority = {
    "00-newsletter": 7,        # curated newsletters are highest signal
    "01-chinese": 6,
    "02-english": 5,
    "03-builder": 4,
    "06-hn-consensus": 3,
    "05-mcp-rss": 2,
    "04-xiaping": 1,
}

files = {
    "00-newsletter": DATA_DIR / "00-newsletter.json",
    "01-chinese": DATA_DIR / "01-chinese.json",
    "02-english": DATA_DIR / "02-english.json",
    "03-builder": DATA_DIR / "03-builder.json",
    "04-xiaping": DATA_DIR / "04-xiaping.json",
    "05-mcp-rss": DATA_DIR / "05-mcp-rss.json",
    "06-hn-consensus": DATA_DIR / "06-hn-consensus.json",
}

all_items = []
loaded_files = []
missing_files = []
for fk, path in files.items():
    if not path.exists():
        missing_files.append(fk)
        continue
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        warnings.warn(f"⚠️ {fk} JSON 不合法: {e}")
        continue
    if not isinstance(data, list):
        warnings.warn(f"⚠️ {fk} 不是数组,跳过")
        continue
    loaded_files.append(fk)
    for item in data:
        item["_file_source"] = fk
        item["_priority"] = source_priority.get(fk, 0)
        all_items.append(item)

print(f"已加载文件: {loaded_files}")
if missing_files:
    print(f"⚠️  缺失文件: {missing_files}（按规则用已有数据继续）")
print(f"原始条目总数: {len(all_items)}")

# --- Step 1: URL exact match dedup ---
url_groups = {}
for item in all_items:
    url = (item.get("url") or "").strip().rstrip("/")
    if not url:
        url = f"_no_url_{id(item)}"
    url_groups.setdefault(url, []).append(item)

deduped_items = []
for url, group in url_groups.items():
    if len(group) == 1:
        deduped_items.append(group[0])
    else:
        group.sort(key=lambda x: x["_priority"], reverse=True)
        kept = group[0]
        kept["cross_validated"] = True
        kept["_cross_sources"] = list({g["_file_source"] for g in group})
        deduped_items.append(kept)
print(f"URL 去重后: {len(deduped_items)}")


# --- Step 2: Title similarity + same-company dedup ---
def normalize_title(t):
    return re.sub(r"[^\w\s]", "", t.lower().strip())


def title_similarity(t1, t2):
    return SequenceMatcher(None, normalize_title(t1), normalize_title(t2)).ratio()


COMPANY_KEYWORDS = [
    "openai", "anthropic", "google", "microsoft", "meta", "apple",
    "nvidia", "cerebras", "deepseek", "alibaba", "tencent", "huawei",
    "runway", "luma", "claude", "gpt", "gemini", "codex", "copilot",
    "langchain", "dify", "kimi", "qwen", "腾讯", "阿里", "华为",
    "英伟达", "tsmc", "台积电", "ibm", "xai", "grok", "pwc",
    "vercel", "openrouter", "fin", "weights", "youtube", "vatican", "教皇",
    "字节", "deepseek", "byte"
]


def extract_companies(item):
    text = (item.get("title", "") + " " + item.get("summary", "")).lower()
    return {k for k in COMPANY_KEYWORDS if k in text}


merged_indices = set()
for i in range(len(deduped_items)):
    if i in merged_indices:
        continue
    for j in range(i + 1, len(deduped_items)):
        if j in merged_indices:
            continue
        sim = title_similarity(deduped_items[i]["title"], deduped_items[j]["title"])
        if sim > 0.8:
            ci = extract_companies(deduped_items[i])
            cj = extract_companies(deduped_items[j])
            if ci & cj or (not ci and not cj):
                hi = deduped_items[i]
                lo = deduped_items[j]
                if hi["_priority"] < lo["_priority"]:
                    hi, lo = lo, hi
                # combine summaries
                hi_summary = hi.get("summary", "") or ""
                lo_summary = lo.get("summary", "") or ""
                if lo_summary and lo_summary not in hi_summary:
                    hi["summary"] = (hi_summary + "；" + lo_summary).strip("；")
                hi["cross_validated"] = True
                hi.setdefault("_cross_sources", [hi["_file_source"]])
                if lo["_file_source"] not in hi["_cross_sources"]:
                    hi["_cross_sources"].append(lo["_file_source"])
                # mark loser merged
                merged_indices.add(j if hi is deduped_items[i] else i)

final_items = [it for k, it in enumerate(deduped_items) if k not in merged_indices]
print(f"标题相似度去重后: {len(final_items)}")

# --- Step 3: Cross-validation across same-company multi-source events ---
for item in final_items:
    if item.get("cross_validated"):
        continue
    companies = extract_companies(item)
    if not companies:
        continue
    related_titles = []
    for other in final_items:
        if other is item:
            continue
        if extract_companies(other) & companies and other["_file_source"] != item["_file_source"]:
            related_titles.append(other["title"])
    if related_titles:
        item["_related_items"] = related_titles[:3]


# --- Step 4: Signal level classification ---
def classify_signal(item):
    title = item.get("title", "").lower()
    summary = item.get("summary", "").lower()
    text = title + " " + summary
    points = item.get("points", 0) or 0

    red_keywords = [
        "ipo", "上市", "市值突破", "trillion", "万亿", "$200m", "$500m", "$1b", "1000亿",
        "格局", "gpt-5", "gpt-6", "重大发布", "历史新高", "breakthrough",
        "140亿", "20亿美元", "2亿美元合作", "billion",
    ]
    for kw in red_keywords:
        if kw in text:
            return "🔴"
    if points > 600:
        return "🔴"

    yellow_keywords = [
        "融资", "raise", "fund", "开源", "open source", "open-source",
        "发布", "launch", "release", "更新", "update", "policy", "通谕",
        "诉讼", "lawsuit", "trial", "安全", "security", "vulnerability",
        "研究", "research", "paper", "论文", "框架", "framework",
        "agent", "智能体", "benchmark", "banned", "ban",
        "扩展", "expand", "投资", "invest", "收购", "acquire",
    ]
    for kw in yellow_keywords:
        if kw in text:
            return "🟡"
    if points > 200:
        return "🟡"
    return "⚪"


# Apply
for item in final_items:
    item["signal_level"] = classify_signal(item)

# Enforce 🔴 ≤ 3
reds = [it for it in final_items if it["signal_level"] == "🔴"]
if len(reds) > 3:
    reds.sort(key=lambda x: (x.get("points", 0) or 0, x["_priority"]), reverse=True)
    for it in reds[3:]:
        it["signal_level"] = "🟡"

# Enforce 🟡 ≤ 10
yellows = [it for it in final_items if it["signal_level"] == "🟡"]
if len(yellows) > 10:
    yellows.sort(key=lambda x: (x.get("points", 0) or 0, x["_priority"]), reverse=True)
    for it in yellows[10:]:
        it["signal_level"] = "⚪"

# Ensure cross_validated field
for item in final_items:
    item.setdefault("cross_validated", False)

# Board coverage
boards = {it.get("board", "?") for it in final_items}
print(f"覆盖 board: {boards} (要求≥4)")

# --- Output ---
output_items = []
for it in final_items:
    out = {
        "title": it.get("title", ""),
        "source": it.get("source", ""),
        "url": it.get("url", ""),
        "summary": it.get("summary", ""),
        "board": it.get("board", ""),
        "date": it.get("date", ""),
        "signal_level": it["signal_level"],
        "cross_validated": it["cross_validated"],
    }
    for k in ("consensus", "action_advice", "points", "comment_count"):
        if k in it:
            out[k] = it[k]
    if "_cross_sources" in it:
        out["_cross_sources"] = it["_cross_sources"]
    output_items.append(out)

out_path = DATA_DIR / "07-merged.json"
out_path.write_text(json.dumps(output_items, ensure_ascii=False, indent=2), encoding="utf-8")

# Stats
sig_dist = {}
board_dist = {}
for it in output_items:
    sig_dist[it["signal_level"]] = sig_dist.get(it["signal_level"], 0) + 1
    board_dist[it["board"]] = board_dist.get(it["board"], 0) + 1
print()
print(f"✅ Goal 7 完成：已写入 {out_path}")
print(f"   合并后总条目数: {len(output_items)}")
print(f"   信号分级分布: {sig_dist}")
print(f"   Board 分布: {board_dist}")
print(f"   交叉验证条目数: {sum(1 for i in output_items if i['cross_validated'])}")
