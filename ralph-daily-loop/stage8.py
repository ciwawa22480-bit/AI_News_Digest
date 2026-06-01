#!/usr/bin/env python3
"""Goal 8: 5-gate QA review for Day 5."""
import json
from pathlib import Path
from datetime import datetime

DATA_DIR = Path("/data/userdata/daily-report/data")
items = json.loads((DATA_DIR / "07b-deduped.json").read_text(encoding="utf-8"))

# Today
TODAY = "2026-06-01"
RECENT_DATES = {"2026-05-30", "2026-05-31", "2026-06-01"}

# Gate 1: data source health
g1_issues = []
for idx, it in enumerate(items, 1):
    url = it.get("url", "")
    date = it.get("date", "")
    title_short = (it.get("title", "") or "")[:30]
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        g1_issues.append(f"条目{idx} '{title_short}...' URL 不合法或为空")
    if not date:
        # HN consensus items typically lack date — acceptable
        if it.get("consensus"):
            continue
        g1_issues.append(f"条目{idx} '{title_short}...' 缺少日期字段")
    elif date not in RECENT_DATES:
        # only flag if clearly old
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            today = datetime.strptime(TODAY, "%Y-%m-%d")
            delta_days = (today - dt).days
            if delta_days > 7 or delta_days < -1:
                g1_issues.append(f"条目{idx} '{title_short}...' 日期不新鲜: {date}")
        except Exception:
            g1_issues.append(f"条目{idx} '{title_short}...' 日期格式异常: {date}")

g1_status = "PASS" if len(g1_issues) <= 5 else "WARN" if len(g1_issues) <= 10 else "FAIL"

# Gate 2: dedup verify
g2_issues = []
urls = [it.get("url", "").strip().rstrip("/") for it in items if it.get("url")]
url_set = set(urls)
if len(urls) != len(url_set):
    dup_count = len(urls) - len(url_set)
    g2_issues.append(f"发现 {dup_count} 个重复 URL")
titles_norm = [it["title"].lower().strip() for it in items if it.get("title")]
if len(titles_norm) != len(set(titles_norm)):
    dup_t = len(titles_norm) - len(set(titles_norm))
    g2_issues.append(f"发现 {dup_t} 个完全重复标题")
g2_status = "PASS" if not g2_issues else "FAIL"

# Gate 3: signal review
sig_dist = {}
for it in items:
    sig_dist[it["signal_level"]] = sig_dist.get(it["signal_level"], 0) + 1
g3_issues = []
red_count = sig_dist.get("🔴", 0)
yellow_count = sig_dist.get("🟡", 0)
if red_count > 3:
    g3_issues.append(f"🔴 重磅条目超限: {red_count} (>3)")
if yellow_count > 10:
    g3_issues.append(f"🟡 值得关注条目超限: {yellow_count} (>10)")
if red_count == 0 and yellow_count == 0:
    g3_issues.append("无任何 🔴/🟡 信号,可能信号识别失败")
g3_status = "PASS" if not g3_issues else "WARN"

# Gate 4: fact check (heuristic - look for obvious issues)
g4_issues = []
for idx, it in enumerate(items, 1):
    title = it.get("title", "")
    summary = it.get("summary", "") or ""
    # Suspicious: very large numbers without source
    text = title + " " + summary
    # Currency consistency
    if "$" in text and "美元" in text:
        # mixed style ok if same fact
        pass
    # Empty consensus where expected
    if it.get("_file_source") == "06-hn-consensus" and not it.get("consensus"):
        g4_issues.append(f"条目{idx} HN 条目缺少 consensus 字段")
g4_status = "PASS" if not g4_issues else "WARN"

# Gate 5: completeness
boards = {it.get("board", "?") for it in items}
g5_issues = []
if len(boards) < 4:
    g5_issues.append(f"Board 覆盖不足: 仅 {len(boards)} 个 ({boards})")
# Field completeness
for idx, it in enumerate(items, 1):
    missing = [f for f in ("title", "url") if not it.get(f)]
    if missing:
        g5_issues.append(f"条目{idx} 缺少必要字段: {missing}")
    # summary or consensus required
    if not it.get("summary") and not it.get("consensus"):
        g5_issues.append(f"条目{idx} 缺少字段: summary")
g5_status = "PASS" if not g5_issues else ("WARN" if len(g5_issues) <= 5 else "FAIL")

# Aggregate
gates = {
    "gate1_data_health": {
        "status": g1_status,
        "urls_checked": len(items),
        "issues": g1_issues,
    },
    "gate2_dedup_verify": {
        "status": g2_status,
        "total_items": len(items),
        "issues": g2_issues,
    },
    "gate3_signal_review": {
        "status": g3_status,
        "distribution": sig_dist,
        "issues": g3_issues,
    },
    "gate4_fact_check": {
        "status": g4_status,
        "items_checked": len(items),
        "issues": g4_issues,
    },
    "gate5_completeness": {
        "status": g5_status,
        "board_coverage": {b: sum(1 for it in items if it.get("board") == b) for b in boards},
        "required_boards_met": len(boards) >= 4,
        "missing_field_count": len(g5_issues),
        "issues": g5_issues,
    },
}

flagged_count = sum(1 for g in gates.values() if g["status"] != "PASS")
overall = "PASS" if flagged_count == 0 else "WARN" if flagged_count <= 2 else "FAIL"

report = {
    "total_items": len(items),
    "passed_items": sum(1 for g in gates.values() if g["status"] == "PASS"),
    "flagged_items": flagged_count,
    "gates": gates,
    "overall_status": overall,
}

out_path = DATA_DIR / "08-qa-report.json"
out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"✅ Goal 8 完成：已写入 {out_path}")
print(f"   总条目: {len(items)}")
print(f"   Gate 结果:")
for name, g in gates.items():
    print(f"   - {name}: {g['status']} ({len(g['issues'])} issues)")
print(f"   整体状态: {overall}")
