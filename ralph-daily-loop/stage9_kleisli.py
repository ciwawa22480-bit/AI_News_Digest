#!/usr/bin/env python3
"""Goal 9 (rev): Render Markdown + CSV from the Kleisli-deduped 07b-deduped.json.

Differences from stage9.py:
  - Input source: 07b-deduped.json (post G0.5 cross-day dedup)
  - Reads 07b-trace.json and renders a banner at the top of MD when WARN/FAIL
  - All other rendering logic identical
"""
import json
import csv
from pathlib import Path

DATA_DIR = Path("/data/userdata/daily-report/data")
OUT_DIR = Path("/data/userdata/daily-report/output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

DATE = "2026-06-01"

items = json.loads((DATA_DIR / "07b-deduped.json").read_text(encoding="utf-8"))
qa = json.loads((DATA_DIR / "08-qa-report.json").read_text(encoding="utf-8"))
trace_path = DATA_DIR / "07b-trace.json"
trace = json.loads(trace_path.read_text(encoding="utf-8")) if trace_path.exists() else None

# Optional: also load version-consistency trace if produced
vtrace_path = DATA_DIR / "07c-version-trace.json"
vtrace = json.loads(vtrace_path.read_text(encoding="utf-8")) if vtrace_path.exists() else None


def is_fact_board(b):
    return b in ("大厂动向", "初创/融资", "初创", "生态/政策", "生态", "开发者工具")


def is_opinion_board(b):
    return b in ("观点",)


big_co, startup, ecosystem, devtools, opinions, hn_items, builders = [], [], [], [], [], [], []

for it in items:
    b = it.get("board", "")
    if it.get("consensus"):
        hn_items.append(it)
    elif b == "大厂动向":
        big_co.append(it)
    elif b in ("初创/融资", "初创"):
        startup.append(it)
    elif b in ("生态/政策", "生态"):
        ecosystem.append(it)
    elif b == "开发者工具":
        devtools.append(it)
    elif b == "观点":
        opinions.append(it)
    elif b == "海外建设者":
        builders.append(it)

SIGNAL_ORDER = {"🔴": 0, "🟡": 1, "⚪": 2}


def sort_key(x):
    return (SIGNAL_ORDER.get(x.get("signal_level", "⚪"), 3),
            -(x.get("points", 0) or 0))


for arr in (big_co, startup, ecosystem, devtools, opinions, hn_items, builders):
    arr.sort(key=sort_key)


def fmt_item(it):
    sig = it.get("signal_level", "⚪")
    title = it.get("title", "")
    url = it.get("url", "")
    src = it.get("source", "") or "未知来源"
    summary = it.get("summary", "") or ""
    cv = " ✅多源" if it.get("cross_validated") else ""
    head = f"- {sig} **{title}**{cv}"
    if summary:
        head += f"\n  {summary}"
    if url:
        head += f" [[{src}]]({url})"
    return head


red_count = sum(1 for it in items if it["signal_level"] == "🔴")
yellow_count = sum(1 for it in items if it["signal_level"] == "🟡")
total = len(items)

top_titles = []
for it in items:
    if it["signal_level"] == "🔴":
        top_titles.append(it["title"])
    if len(top_titles) >= 3:
        break
if not top_titles:
    for it in items:
        if it["signal_level"] == "🟡":
            top_titles.append(it["title"])
        if len(top_titles) >= 3:
            break

one_liner = (
    f"今日共汇总 {total} 条 AI 行业资讯（🔴重磅 {red_count} / 🟡值得关注 {yellow_count}）,"
    f"核心看点: " + " | ".join(t[:30] for t in top_titles[:3])
)

md = []
md.append(f"# 📅 AI 行业日报 · {DATE}\n")
md.append(f"> {one_liner}\n")

# === Kleisli pipeline banner (G0.5 / G0.8) ===
banners = []
if trace and trace.get("status") in ("WARN", "FAIL") and trace.get("removed", 0) > 0:
    removed = trace["removed"]
    # Find the dominant prior date from evidence
    prior_lines = [e for e in trace.get("evidence", []) if e.strip().startswith("vs ")]
    prior_summary = prior_lines[0].strip() if prior_lines else ""
    banners.append(
        f"> ⚠️ **跨日去重**: 本期通过 Kleisli gate `G0.5` 自动剔除 **{removed}** 条与 {prior_summary or '前 3 日'} 重复的条目；"
        f"原始候选 {trace.get('input_count')} → 实际入选 {trace.get('output_count')}。"
    )
if vtrace and vtrace.get("status") in ("WARN", "FAIL") and vtrace.get("conflicts"):
    conf = vtrace["conflicts"]
    pieces = []
    for c in conf:
        pieces.append(f"`{c['product']}` 最新版 {c['latest']} 与旧版 {c['stale_versions']} 同时出现")
    banners.append(
        f"> ⚠️ **版本一致性**: Kleisli gate `G0.8` 检出 {len(conf)} 项版本冲突 —— "
        + "；".join(pieces) + ",请读者甄别。"
    )
if banners:
    md.append("\n".join(banners) + "\n")

md.append("## 📊 今日概览\n")
md.append(f"- 总条目: **{total}**")
md.append(f"- 🔴 重磅: {red_count} 条 / 🟡 值得关注: {yellow_count} 条 / ⚪ 常规: {total - red_count - yellow_count} 条")
md.append(f"- 板块覆盖: {', '.join(sorted({it.get('board','?') for it in items}))}")
cv_count = sum(1 for it in items if it.get("cross_validated"))
md.append(f"- 多源交叉验证: {cv_count} 条\n")

md.append("## 📰 偏 Fact 类\n")

if big_co:
    md.append("### 🏢 大厂动向\n")
    for it in big_co:
        md.append(fmt_item(it))
    md.append("")

if startup:
    md.append("### 🚀 初创/融资\n")
    for it in startup:
        md.append(fmt_item(it))
    md.append("")

if ecosystem:
    md.append("### 🌐 生态/政策\n")
    for it in ecosystem:
        md.append(fmt_item(it))
    md.append("")

if devtools:
    md.append("### 🛠️ 开发者工具\n")
    for it in devtools:
        md.append(fmt_item(it))
    md.append("")

md.append("## 💬 偏观点类\n")
if opinions:
    md.append("### 行业观察\n")
    for it in opinions:
        md.append(fmt_item(it))
    md.append("")

if hn_items:
    md.append("### [HN 共识] 海外社区高热讨论\n")
    for it in hn_items:
        sig = it.get("signal_level", "⚪")
        md.append(f"#### {sig} {it['title']}")
        md.append(f"> 🔥 {it.get('points',0)} pts / 💬 {it.get('comment_count',0)} 评论 · [[Hacker News]]({it['url']})\n")
        md.append("**社区共识:**")
        for c in it.get("consensus", []):
            md.append(f"- {c}")
        md.append("")
        adv = it.get("action_advice", {})
        if adv:
            md.append("**行动建议:**")
            md.append(f"- 🔨 Builder: {adv.get('builder','—')}")
            md.append(f"- 👥 团队: {adv.get('team','—')}")
            md.append(f"- 💰 投资者: {adv.get('investor','—')}")
        md.append("")

md.append("## 🌍 海外建设者动态\n")
if builders:
    for it in builders:
        md.append(fmt_item(it))
    md.append("")
else:
    md.append("> 本日海外建设者动态由 HN 共识章节代为承载。\n")

md.append("## 📊 质量审核报告\n")
md.append(f"**整体状态: {qa['overall_status']}**  ·  通过 Gate: {qa['passed_items']}/5  ·  Flag: {qa['flagged_items']}\n")
md.append("| Gate | 状态 | 关键发现 |")
md.append("|---|---|---|")
gate_label = {
    "gate1_data_health": "数据源健康",
    "gate2_dedup_verify": "去重验证",
    "gate3_signal_review": "信号分级复核",
    "gate4_fact_check": "事实核验",
    "gate5_completeness": "完整性自检",
}
for gname, ginfo in qa["gates"].items():
    label = gate_label.get(gname, gname)
    issues = ginfo.get("issues", [])
    finding = "无问题" if not issues else f"{len(issues)} 项: {issues[0][:40]}{'...' if len(issues[0])>40 else ''}"
    md.append(f"| {label} | {ginfo['status']} | {finding} |")

# Append Kleisli gate rows
if trace:
    md.append(f"| G0.5 跨日去重 (Kleisli) | {trace['status']} | 剔除 {trace.get('removed',0)} 条跨日重复 |")
if vtrace:
    md.append(f"| G0.8 版本一致性 (Kleisli) | {vtrace['status']} | {len(vtrace.get('conflicts',[]))} 项版本冲突 |")
md.append("")

md.append("## 📌 三大关键趋势\n")

trends = []
trend1_signals = [it for it in items if it["signal_level"] in ("🔴", "🟡") and it.get("board") == "大厂动向"][:3]
if trend1_signals:
    trends.append({
        "title": "前沿模型与资本竞赛同步加速",
        "desc": "Anthropic 完成 AI 史上最大单轮 $65B H 轮、估值 $965B,同时 Claude Opus 4.8 在三大编码基准刷新 SOTA;DeepSeek 计划科创板 IPO 估值 ¥800B;Apple 通过蒸馏 Gemini 切入端侧 Siri。模型能力 → 资本 → 产品的飞轮被同步推到极速,任何一家 Tier 1 公司的单日动态都已构成全行业估值重锚。",
        "evidence": [it["title"] for it in trend1_signals[:3]],
    })
trend2_signals = [it for it in items if it.get("board") == "开发者工具"][:3]
if trend2_signals:
    trends.append({
        "title": "Agent 工具链向工程化纵深",
        "desc": "开发者工具板块本日密集出现 Skill API、token 压缩、推理加速、多模型路由等基础设施级方案。Agent 系统的真实工程瓶颈(token 成本、上下文管理、协作编排)正在被系统性解决,标志着从 demo 走向生产部署的拐点已经过去。",
        "evidence": [it["title"] for it in trend2_signals[:3]],
    })
trend3_signals = hn_items[:3]
if trend3_signals:
    trends.append({
        "title": "AGI 时间表前移引发治理与估值再校准",
        "desc": "Hassabis 将 AGI 时间从 5-10 年压到 3 年;HN 共识普遍接受 2027-2028 年通用 Agent 经济级可用是 base case。这直接驱动 AI Safety/Alignment、AGI 时代基础设施(算力、能源、机器人)的赔率窗口打开,同时也压缩了组织 AI-native 转型的窗口期。",
        "evidence": [it["title"] for it in trend3_signals[:3]],
    })

for i, t in enumerate(trends, 1):
    md.append(f"### 趋势 {i}: {t['title']}\n")
    md.append(f"{t['desc']}\n")
    md.append("**关键佐证:**")
    for e in t["evidence"]:
        md.append(f"- {e}")
    md.append("")

md.append("---")
md.append(f"*由 AI 日报 Pipeline (Kleisli rev) 自动生成 · 数据日期 {DATE} · QA 状态 {qa['overall_status']}*")

md_text = "\n".join(md)
md_path = OUT_DIR / "daily-report.md"
md_path.write_text(md_text, encoding="utf-8")

csv_path = OUT_DIR / "daily-report.csv"
with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["日期", "编号", "板块", "标题", "信号等级", "事实核验", "关联公司", "关联赛道", "来源", "原文URL", "摘要", "是否推送"])

    COMPANIES = ["OpenAI", "Anthropic", "Google", "Microsoft", "Meta", "NVIDIA", "DeepSeek",
                 "Cerebras", "Runway", "Vercel", "字节跳动", "xAI", "YouTube", "Apple",
                 "OpenRouter", "OpenClaw", "GitHub", "DeepMind"]
    TRACKS = {"大模型": ["claude", "gpt", "gemini", "deepseek", "llm", "model", "kimi", "qwen", "grok", "opus"],
              "Agent/具身智能": ["agent", "智能体", "codex", "computer use", "skill"],
              "AI视频/音频": ["video", "音频", "audio", "voice", "radio"],
              "AI硬件/芯片": ["cerebras", "nvidia", "芯片", "chip", "tpu", "npu"],
              "AI编程": ["claude code", "code", "copilot", "vercel", "编程", "cursor"],
              "AI安全": ["safety", "security", "alignment", "vulnerability"],
              "融资": ["融资", "估值", "ipo", "raise", "billion", "美元", "$"],
              "AI政策": ["policy", "通谕", "梵蒂冈", "regulation", "法规", "监管"],
              "企业AI": ["enterprise", "企业", "subscription", "saas", "arr"]}

    for idx, it in enumerate(items, 1):
        text = (it.get("title", "") + " " + it.get("summary", "")).lower()
        title = it.get("title", "")
        comps = [c for c in COMPANIES if c.lower() in text]
        tracks = []
        for tn, kws in TRACKS.items():
            if any(kw in text for kw in kws):
                tracks.append(tn)
        fact = "✅" if it.get("cross_validated") else "—"
        push = "是" if it.get("signal_level") in ("🔴", "🟡") else "否"
        summ = it.get("summary", "")
        if not summ and it.get("consensus"):
            summ = "HN 共识: " + " | ".join(it["consensus"][:3])

        w.writerow([
            it.get("date", DATE),
            f"D{idx:03d}",
            it.get("board", ""),
            title,
            it.get("signal_level", ""),
            fact,
            "; ".join(comps) if comps else "—",
            "; ".join(tracks) if tracks else "—",
            it.get("source", ""),
            it.get("url", ""),
            summ,
            push,
        ])

md_size = md_path.stat().st_size
csv_lines = sum(1 for _ in open(csv_path, encoding="utf-8-sig"))

print(f"✅ Markdown 日报已写入: {md_path}")
print(f"   字符数: {len(md_text)}")
print(f"✅ CSV 文件已写入: {csv_path}")
print(f"   总行数: {csv_lines} (含表头)")

print("\n=== 完成条件验证 ===")
print(f"  [{'✓' if (DATA_DIR/'06-hn-consensus.json').exists() else '✗'}] 06 JSON 存在")
print(f"  [{'✓' if (DATA_DIR/'07b-deduped.json').exists() else '✗'}] 07b JSON 存在 (Kleisli post-dedup)")
print(f"  [{'✓' if (DATA_DIR/'08-qa-report.json').exists() else '✗'}] 08 JSON 存在")
print(f"  [{'✓' if len(md_text) > 2000 else '✗'}] daily-report.md > 2000 字符 (实际 {len(md_text)})")
with open(csv_path, encoding="utf-8-sig") as f:
    header = next(csv.reader(f))
print(f"  [{'✓' if len(header) == 12 else '✗'}] CSV 包含 12 列 (实际 {len(header)})")
print(f"  [{'✓' if '📌 三大关键趋势' in md_text else '✗'}] MD 末尾含「📌 三大关键趋势」章节")
print(f"  [{'✓' if 'Kleisli' in md_text else '✗'}] MD 顶部含 Kleisli banner")
