#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_html.py

将 AI 精选资讯渲染为中文商业日报静态网页。

本版本重点升级：
- 顶部：整段编辑概述（不再是一句话）
- 新增「本期要点概述」：三维结论（新产品功能 / 网上观点 / 行业生态）
- 单条渲染时过滤空话/水字数要点（防御旧数据）
- 历史归档：为每一天生成独立、排版精美的 HTML 页面（archive/<date>.html），
  点击历史日期打开的是正常网页，而不是裸 JSON 列表。
"""
import os
import json
import html
import re
import shutil
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DAILY_DIR = os.path.join(DATA_DIR, "daily")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ARCHIVE_DIR = os.path.join(OUTPUT_DIR, "archive")

NEWS_FILE = os.path.join(DATA_DIR, "news_items.json")
WEEKLY_FILE = os.path.join(DATA_DIR, "weekly_items.json")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")

CATEGORY_ORDER = ["大厂动向", "初创动向", "生态动向", "观点与深度"]

FILLER_POINT_PATTERNS = [
    "关注其对竞争格局与商业化节奏的影响",
    "头部公司动作，关注其对行业标准与广告营销场景的辐射",
    "资本与融资动向，关注新玩家的商业模式与落地场景",
    "行业观点/数据，可用于判断趋势与市场空间",
    "生态/政策/基础设施变化，关注对上下游与合规的影响",
]


def esc(text):
    if text is None:
        return ""
    return html.escape(str(text))


def load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def impact_dot(impact):
    if impact == "high":
        return '<span class="dot dot-high" title="高影响"></span>'
    elif impact == "medium":
        return '<span class="dot dot-medium" title="中影响"></span>'
    return '<span class="dot dot-low" title="信息流"></span>'


def clean_points(points):
    """渲染层防御：去掉空话/纯公司名罗列/重复的要点。"""
    cleaned = []
    seen = set()
    for p in points or []:
        if not p or not str(p).strip():
            continue
        p = str(p).strip()
        if re.match(r"^涉及公司[:：]", p) and "，" not in p.rstrip("。"):
            continue
        if any(fp in p for fp in FILLER_POINT_PATTERNS):
            continue
        key = p[:20]
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(p)
    return cleaned[:3]


def build_item_html(item):
    title = item.get("title", "")
    explanation = item.get("explanation", item.get("summary", ""))
    analysis_points = clean_points(item.get("analysis_points", []))
    impact = item.get("impact", "medium")
    source = item.get("source", "")
    url = item.get("url", "")
    local_hint = item.get("local_life_hint", "")

    if url:
        title_html = '<a href="' + esc(url) + '" target="_blank" class="item-link">' + esc(title) + '</a>'
    else:
        title_html = '<span class="item-title-text">' + esc(title) + '</span>'

    exp_html = ""
    if explanation:
        exp_html = '<div class="item-explanation">' + esc(explanation) + '</div>'

    points_html = ""
    if analysis_points:
        pts = "".join('<li>' + esc(pt) + '</li>' for pt in analysis_points if pt)
        if pts:
            points_html = '<ul class="analysis-points">' + pts + '</ul>'

    local_html = ""
    if local_hint:
        local_html = '<div class="local-hint"><span class="local-tag">营销启发</span>' + esc(local_hint) + '</div>'

    source_html = ""
    if source:
        source_html = '<span class="item-source">(' + esc(source) + ')</span>'

    return "".join([
        '<div class="news-item">',
        '<div class="item-main">',
        impact_dot(impact),
        title_html,
        source_html,
        '</div>',
        exp_html,
        points_html,
        local_html,
        '</div>',
    ])


def build_category_block(category, type_label, items, summary=""):
    if not items:
        return ""
    items_html = "\n".join([build_item_html(it) for it in items])
    summary_html = ""
    if summary:
        summary_html = '<div class="cat-summary">' + esc(summary) + '</div>'
    return "".join([
        '<tr class="category-row">',
        '<td class="col-type"><span class="type-label">', esc(type_label), '</span></td>',
        '<td class="col-category"><span class="cat-label">', esc(category), '</span></td>',
        '<td class="col-content">', summary_html, items_html, '</td>',
        '</tr>',
    ])


def build_commonality_html(commonality):
    """周报「共性提炼」板块：把 list[str] 渲染成有序列表；空则不显示。"""
    if not commonality:
        return ""
    items = [c for c in commonality if c and str(c).strip()]
    if not items:
        return ""
    lis = "".join('<li>' + esc(c) + '</li>' for c in items)
    return ('<section class="commonality-section">'
            '<h3 class="commonality-title">共性提炼</h3>'
            '<div class="commonality-tip">跨条目的高频主题与趋势结论</div>'
            '<ul class="commonality-list">' + lis + '</ul>'
            '</section>')


def build_overview_html(overview):
    """三维结论：新产品功能 / 网上观点 / 行业生态。"""
    if not overview:
        return ""
    dims = [
        ("new_products", "🚀 新产品功能", "哪个公司有什么新功能、具体怎么实现"),
        ("opinions", "💬 网上观点", "报道/分析师的新观点与论据"),
        ("ecosystem", "🌐 行业生态", "基于这些文章看到的行业态势"),
    ]
    blocks = ""
    for key, label, hint in dims:
        arr = [a for a in (overview.get(key) or []) if a and str(a).strip()]
        if not arr:
            continue
        lis = "".join('<li>' + esc(a) + '</li>' for a in arr)
        blocks += ('<div class="ov-block"><div class="ov-head">' + label
                   + '<span class="ov-hint">' + esc(hint) + '</span></div>'
                   + '<ul class="ov-list">' + lis + '</ul></div>')
    if not blocks:
        return ""
    return ('<section class="overview-section">'
            '<h3 class="overview-title">本期要点概述</h3>'
            + blocks + '</section>')


def build_local_life_insights(insights, intro=""):
    """外投团队借鉴（技术底座视角）。支持两种条目：{base,borrow} 结构 或 纯字符串。"""
    if not insights:
        return ""
    cards = ""
    for ins in insights:
        if not ins:
            continue
        if isinstance(ins, dict):
            base = ins.get("base", "")
            borrow = ins.get("borrow", "")
            if not base and not borrow:
                continue
            cards += ('<div class="takeaway">'
                      '<div class="tw-base"><span class="tw-tag tw-tag-base">技术底座变化</span>' + esc(base) + '</div>'
                      '<div class="tw-borrow"><span class="tw-tag tw-tag-borrow">对外投的借鉴</span>' + esc(borrow) + '</div>'
                      '</div>')
        else:
            cards += '<div class="takeaway"><div class="tw-borrow">' + esc(ins) + '</div></div>'
    if not cards:
        return ""
    intro_html = ('<p class="insights-intro">' + esc(intro) + '</p>') if intro else ""
    return "".join([
        '<section class="insights-section">',
        '<h3 class="insights-title">外投团队的借鉴 · 技术底座视角</h3>',
        intro_html,
        '<div class="takeaway-list">',
        cards,
        '</div>',
        '</section>',
    ])


def build_content_view(data):
    if not data or not data.get("items"):
        return '<div class="empty">暂无数据</div>'

    items = data.get("items", [])
    editorial = data.get("editorial_summary", "")
    overview = data.get("overview", {}) or {}
    category_summaries = data.get("category_summaries", {}) or {}
    local_life_insights = data.get("local_life_insights", []) or []
    commonality = data.get("commonality", []) or []

    editorial_html = ""
    if editorial:
        editorial_html = ('<div class="editorial">'
                          '<div class="editorial-head">'
                          '<span class="editorial-label">编辑导读</span>'
                          '</div>'
                          '<div class="editorial-body">' + esc(editorial) + '</div>'
                          '</div>')

    overview_html = build_overview_html(overview)
    commonality_html = build_commonality_html(commonality)

    grouped = {}
    for item in items:
        cat = item.get("category", "大厂动向")
        grouped.setdefault(cat, []).append(item)

    fact_categories = ["大厂动向", "初创动向", "生态动向"]

    rows = ""
    for cat in CATEGORY_ORDER:
        if cat not in grouped:
            continue
        type_label = "偏fact类" if cat in fact_categories else "偏观点类"
        rows += build_category_block(cat, type_label, grouped[cat], category_summaries.get(cat, ""))
    for cat in grouped:
        if cat not in CATEGORY_ORDER:
            rows += build_category_block(cat, "偏fact类", grouped[cat], category_summaries.get(cat, ""))

    total = len(items)
    high_count = len([i for i in items if i.get("impact") == "high"])
    # 较昨日（上一份日报）新增条目数标记
    new_cnt = data.get("new_vs_yesterday")
    cmp_date = data.get("compare_date", "")
    new_badge = ""
    if isinstance(new_cnt, int):
        tip = ("对比 " + esc(cmp_date) + " 日报去重后统计") if cmp_date else "对比上一份日报"
        new_badge = (' · <span class="new-badge" title="' + tip + '">▲ 较昨日新增 '
                     + str(new_cnt) + ' 条</span>')
    stats_html = ('<div class="stats">共 ' + str(total) + ' 条精选 · '
                  + str(high_count) + ' 条高影响' + new_badge + '</div>')

    insights_html = build_local_life_insights(local_life_insights, data.get("insights_intro", ""))

    return "".join([
        editorial_html,
        overview_html,
        commonality_html,
        '<div class="signal-legend">',
        '信号等级：',
        '<span class="dot dot-high"></span>高影响 / ',
        '<span class="dot dot-medium"></span>中影响 / ',
        '<span class="dot dot-low"></span>信息流',
        '</div>',
        stats_html,
        '<table class="digest-table"><tbody>',
        rows,
        '</tbody></table>',
        insights_html,
    ])


def build_archive_section(current_date=None, prefix=""):
    """按周分组的归档区。链接指向已渲染的 archive/<date>.html 网页（而非裸 JSON）。"""
    if not os.path.isdir(DAILY_DIR):
        return ""
    files = sorted([f for f in os.listdir(DAILY_DIR) if f.endswith(".json")], reverse=True)
    if not files:
        return ""

    beijing = timezone(timedelta(hours=8))
    weeks = {}
    for f in files[:90]:
        date_str = f.replace(".json", "")
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=beijing)
            monday = dt - timedelta(days=dt.weekday())
            week_key = monday.strftime("%m.%d") + "-" + (monday + timedelta(days=6)).strftime("%m.%d")
            month_key = dt.strftime("%Y年%m月")
            weeks.setdefault(month_key, {}).setdefault(week_key, []).append(date_str)
        except Exception:
            continue

    archive_html = ""
    for month, week_groups in list(weeks.items())[:3]:
        archive_html += '<div class="archive-month"><h4>' + esc(month) + '</h4>'
        for week_range, dates in week_groups.items():
            archive_html += '<div class="archive-week"><span class="week-label">' + esc(week_range) + '</span>'
            for d in dates:
                active = ' date-link-active' if d == current_date else ''
                archive_html += ('<a href="' + prefix + 'archive/' + esc(d) + '.html" '
                                 'class="date-link' + active + '">' + esc(d.split("-", 1)[1]) + '</a>')
            archive_html += '</div>'
        archive_html += '</div>'

    return "".join([
        '<section class="archive-section">',
        '<h3 class="archive-title">历史归档</h3>',
        '<div class="archive-tip">点击任意日期查看当天完整日报（已排版，非原始数据）</div>',
        archive_html,
        '</section>',
    ])


PAGE_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { min-height: 100%; }
body { font-family: "Noto Sans SC", -apple-system, sans-serif; background: #f7f9fc; color: #1a1a1a; line-height: 1.7; font-size: 14px; position: relative; overflow-x: hidden; }
/* 浅色专业风底：柔和径向光晕做底，粒子由 #particle-bg canvas 叠加，无廉价网格 */
body::before {
  content: "";
  position: fixed;
  inset: 0;
  z-index: -2;
  pointer-events: none;
  background-color: #f7f9fc;
  background-image:
    radial-gradient(1200px 700px at 12% -5%, rgba(99,102,241,0.10) 0%, transparent 55%),
    radial-gradient(1000px 620px at 100% 8%, rgba(56,189,248,0.08) 0%, transparent 55%),
    radial-gradient(900px 560px at 88% 100%, rgba(255,195,0,0.07) 0%, transparent 55%);
}
/* 粒子背景 canvas：铺满视口、固定、置于内容下方 */
#particle-bg {
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: -1;
  pointer-events: none;
  display: block;
}
.header { padding: 32px 40px 20px; border-bottom: 1px solid #e5e7eb; background: rgba(255,255,255,0.72); backdrop-filter: blur(4px); position: relative; }
.header h1 { font-size: 22px; font-weight: 700; color: #111; margin-bottom: 4px; }
.header .subtitle { font-size: 13px; color: #4f46e5; font-weight: 500; margin-bottom: 6px; }
.header .date-line { font-size: 14px; color: #666; }
.header .mode-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; background: #f0f9ff; color: #0369a1; margin-left: 8px; }
.header .back-link { display: inline-block; margin-top: 10px; font-size: 13px; color: #4f46e5; text-decoration: none; }
.header .back-link:hover { text-decoration: underline; }
/* 美团黄袋鼠吉祥物：header 右上角点缀，缓慢上下浮动 */
.roo-mascot { position: absolute; top: 22px; right: 28px; width: 52px; height: 52px; animation: roo-hop 3.6s ease-in-out infinite; pointer-events: none; filter: drop-shadow(0 2px 4px rgba(255,195,0,0.28)); }
@keyframes roo-hop {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-3px); }
}
.toggle-bar { padding: 12px 40px 0; display: flex; gap: 0; border-bottom: 1px solid #e5e7eb; background: rgba(255,255,255,0.72); }
.tab { padding: 8px 24px; border: none; background: none; font-size: 14px; color: #666; cursor: pointer; border-bottom: 2px solid transparent; font-weight: 500; }
.tab.active { color: #4f46e5; border-bottom-color: #4f46e5; }
.container { max-width: 1100px; margin: 0 auto; padding: 24px 40px; background: transparent; }
.editorial { padding: 16px 20px; background: #f8fafc; border-left: 4px solid #4f46e5; border-radius: 0 8px 8px 0; margin-bottom: 20px; font-size: 15px; color: #1e293b; line-height: 1.85; }
.editorial-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 6px; flex-wrap: wrap; }
.editorial-body { }
.editorial-label { display: inline-block; font-weight: 700; color: #4f46e5; margin-right: 8px; }
/* Overview 三维结论 */
.overview-section { margin-bottom: 24px; padding: 20px 22px; background: linear-gradient(135deg,#eef2ff 0%,#f5f3ff 100%); border: 1px solid #e0e7ff; border-radius: 12px; }
.overview-title { font-size: 16px; font-weight: 700; color: #3730a3; margin-bottom: 14px; display: flex; align-items: center; }
.overview-title::before { content: ""; display: inline-block; width: 5px; height: 17px; background: #6366f1; border-radius: 3px; margin-right: 10px; }
.ov-block { margin-bottom: 14px; }
.ov-block:last-child { margin-bottom: 0; }
.ov-head { font-size: 14px; font-weight: 600; color: #4338ca; margin-bottom: 6px; }
.ov-hint { font-size: 11px; font-weight: 400; color: #818cf8; margin-left: 8px; }
.ov-list { margin: 0 0 0 20px; padding: 0; list-style: disc; }
.ov-list li { font-size: 13.5px; color: #334155; line-height: 1.7; margin-bottom: 4px; }
/* 共性提炼板块（周报）：低调的浅青底 */
.commonality-section { margin-bottom: 24px; padding: 18px 22px; background: linear-gradient(135deg,#ecfeff 0%,#f0f9ff 100%); border: 1px solid #bae6fd; border-radius: 12px; }
.commonality-title { font-size: 16px; font-weight: 700; color: #075985; margin-bottom: 4px; display: flex; align-items: center; }
.commonality-title::before { content: ""; display: inline-block; width: 5px; height: 17px; background: #0ea5e9; border-radius: 3px; margin-right: 10px; }
.commonality-tip { font-size: 12px; color: #0369a1; margin-bottom: 10px; }
.commonality-list { margin: 0 0 0 22px; padding: 0; list-style: disc; }
.commonality-list li { font-size: 13.5px; color: #0c4a6e; line-height: 1.7; margin-bottom: 4px; }
.signal-legend { font-size: 12px; color: #64748b; margin-bottom: 8px; display: flex; align-items: center; gap: 4px; }
.stats { font-size: 12px; color: #94a3b8; margin-bottom: 16px; }
.new-badge { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; color: #047857; background: #ecfdf5; border: 1px solid #a7f3d0; cursor: help; }
.cat-summary { font-size: 13px; color: #475569; background: #f8fafc; border-left: 3px solid #94a3b8; padding: 8px 12px; border-radius: 0 6px 6px 0; margin-bottom: 14px; line-height: 1.7; }
.insights-section { margin-top: 32px; padding: 24px 28px; background: linear-gradient(135deg, #fff7ed 0%, #fef3c7 100%); border: 1px solid #fde68a; border-radius: 12px; }
.insights-title { font-size: 17px; font-weight: 700; color: #b45309; margin-bottom: 16px; display: flex; align-items: center; }
.insights-title::before { content: ""; display: inline-block; width: 5px; height: 18px; background: #f59e0b; border-radius: 3px; margin-right: 10px; }
.insights-intro { font-size: 13.5px; color: #92400e; line-height: 1.8; margin-bottom: 16px; }
.takeaway-list { display: flex; flex-direction: column; gap: 12px; }
.takeaway { background: #fffdf7; border: 1px solid #fde68a; border-radius: 8px; padding: 12px 14px; }
.tw-base { font-size: 13px; color: #7c2d12; line-height: 1.7; margin-bottom: 6px; }
.tw-borrow { font-size: 13.5px; color: #78350f; font-weight: 500; line-height: 1.75; }
.tw-tag { display: inline-block; font-size: 11px; font-weight: 700; padding: 1px 8px; border-radius: 4px; margin-right: 8px; vertical-align: middle; }
.tw-tag-base { background: #fef3c7; color: #b45309; }
.tw-tag-borrow { background: #f59e0b; color: #fff; }
.insights-list { list-style: none; padding: 0; margin: 0; }
.insight-item { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 12px; font-size: 14px; color: #78350f; line-height: 1.7; }
.insight-item:last-child { margin-bottom: 0; }
.insight-num { flex-shrink: 0; width: 22px; height: 22px; border-radius: 50%; background: #f59e0b; color: #fff; font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center; margin-top: 1px; }
.insight-text { flex: 1; font-weight: 500; }
.dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; flex-shrink: 0; }
.dot-high { background: #ef4444; }
.dot-medium { background: #f59e0b; }
.dot-low { background: #cbd5e1; }
.digest-table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; }
.category-row td { padding: 16px 12px; vertical-align: top; border-top: 1px solid #e5e7eb; }
.col-type { width: 70px; text-align: center; }
.col-category { width: 90px; text-align: center; }
.col-content { padding-left: 20px !important; }
.type-label { font-size: 12px; color: #64748b; font-weight: 500; white-space: nowrap; }
.cat-label { font-size: 13px; font-weight: 600; color: #1e293b; white-space: nowrap; }
.news-item { margin-bottom: 18px; }
.news-item:last-child { margin-bottom: 0; }
.item-main { display: flex; flex-wrap: wrap; align-items: flex-start; gap: 4px; }
.item-main .dot { margin-top: 6px; }
.item-link { color: #1e40af; text-decoration: none; font-weight: 600; font-size: 14px; }
.item-link:hover { text-decoration: underline; }
.item-title-text { font-weight: 600; font-size: 14px; color: #1e293b; }
.item-explanation { color: #374151; font-size: 13.5px; margin: 4px 0 0 14px; }
.item-source { color: #94a3b8; font-size: 11px; }
.analysis-points { margin: 6px 0 0 34px; padding: 0; list-style: disc; }
.analysis-points li { font-size: 13px; color: #4b5563; line-height: 1.6; margin-bottom: 3px; }
.local-hint { margin: 6px 0 0 34px; padding: 4px 10px; background: #f0fdfa; border: 1px solid #ccfbf1; border-radius: 4px; font-size: 12px; color: #0f766e; }
.local-tag { font-weight: 600; margin-right: 6px; color: #14b8a6; }
.archive-section { margin-top: 40px; padding-top: 24px; border-top: 1px solid #e5e7eb; }
.archive-title { font-size: 15px; font-weight: 600; color: #374151; margin-bottom: 4px; }
.archive-tip { font-size: 12px; color: #94a3b8; margin-bottom: 12px; }
.archive-month { margin-bottom: 12px; }
.archive-month h4 { font-size: 13px; color: #64748b; margin-bottom: 6px; }
.archive-week { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap; }
.week-label { font-size: 12px; color: #94a3b8; min-width: 80px; }
.date-link { font-size: 12px; color: #6366f1; text-decoration: none; padding: 2px 8px; border-radius: 4px; background: #f5f3ff; }
.date-link:hover { background: #ede9fe; }
.date-link-active { background: #6366f1; color: #fff; }
.footer { padding: 24px 40px; text-align: center; color: #94a3b8; font-size: 11px; border-top: 1px solid #f1f5f9; margin-top: 32px; background: rgba(255,255,255,0.6); }
.empty { text-align: center; padding: 60px; color: #94a3b8; }
@media (max-width: 768px) {
  .header, .container, .footer { padding-left: 16px; padding-right: 16px; }
  .toggle-bar { padding-left: 16px; }
  .col-type, .col-category { display: none; }
  .col-content { padding-left: 0 !important; }
  .category-row td { padding: 12px 0; }
  .roo-mascot { width: 40px; height: 40px; top: 16px; right: 12px; }
  .editorial-head { flex-direction: column; align-items: flex-start; gap: 6px; }
}
"""


ROO_SVG = """<svg class="roo-mascot" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="美团黄袋鼠">
<defs>
<linearGradient id="rooGrad" x1="0" x2="0" y1="0" y2="1">
<stop offset="0" stop-color="#FFD100"/>
<stop offset="1" stop-color="#FFC300"/>
</linearGradient>
</defs>
<!-- 耳朵 -->
<path fill="#FFC300" d="M35 7c1-1 3-1 3 1 0 3-1 6-3 8-2 1-3 0-3-2 0-2 1-5 3-7z"/>
<path fill="#FFC300" d="M41 9c1-1 3 0 3 2 0 3-1 5-3 7-1 1-3 1-3-1 0-3 1-6 3-8z"/>
<!-- 头 -->
<circle cx="41" cy="20" r="7" fill="url(#rooGrad)"/>
<!-- 眼睛 -->
<circle cx="43" cy="19" r="1.4" fill="#222"/>
<!-- 身体+尾巴（一笔剪影） -->
<path fill="url(#rooGrad)" d="M36 26c-6 0-11 4-13 10-1 3-3 6-6 8-2 2-4 3-5 5-1 1 0 3 2 3h13c2 0 3-1 3-3 0-2 1-4 3-5 3-2 6-2 9-2 3 0 5-2 5-5 0-2-1-4-3-5l-3-1c-2-1-3-3-5-5z"/>
<!-- 前爪 -->
<path fill="#E6A800" d="M31 33c1-1 3-1 4 0 1 1 1 3 0 3l-4 1c-1 0-1-3 0-4z"/>
</svg>"""


def render_page(title_suffix, header_date_line, body_html, toggle_html="",
                switch_script="", back_link_html="", gen_time=""):
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI 商业日报 · """ + esc(title_suffix) + """</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>""" + PAGE_CSS + """</style>
</head>
<body>
<canvas id="particle-bg" aria-hidden="true"></canvas>
<div class="header">
""" + ROO_SVG + """
<h1>AI 商业日报</h1>
<div class="subtitle">字节系 AI 商业化动态 · DeepSeek 精选</div>
<div class="date-line">""" + header_date_line + """</div>
""" + back_link_html + """
</div>
""" + toggle_html + """
<div class="container">
""" + body_html + """
</div>
<div class="footer">
每日自动更新 · 聚焦字节跳动全系 AI 商业化（豆包 / 火山引擎 / 扣子 Coze / 即梦 / 剪映 / 巨量引擎 / TikTok 等）<br>
数据来源：Google News（中英）/ 36氪 / IT之家 / 爱范儿 / cnBeta / TechCrunch / VentureBeat / The Verge / The Rundown / HN / AI热点<br>
生成于 """ + gen_time + """
</div>
""" + particle_bg_script() + """
""" + switch_script + """
</body>
</html>"""


def particle_bg_script():
    """浅色专业风的 canvas 粒子背景。

    设计目标：
    - 浅色、克制、专业，不喧宾夺主（低不透明度、柔和靛蓝/琥珀点缀色）；
    - 轻量粒子在慢速漂移，邻近粒子间用极淡连线，形成"科技网络"质感；
    - 粒子数量随屏幕面积自适应并设上限，移动端进一步降密度；
    - 尊重 prefers-reduced-motion，减少动态；
    - devicePixelRatio 适配，避免高分屏模糊；resize 时重建。
    """
    return """<script>
(function(){
  var canvas = document.getElementById('particle-bg');
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext('2d');
  var reduce = false;
  try {
    reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch(e) {}

  var dpr = Math.max(1, Math.min(window.devicePixelRatio || 1, 2));
  var W = 0, H = 0, particles = [], raf = null;
  // 浅色专业配色：靛蓝为主，少量美团黄点缀
  var COLORS = ['99,102,241', '99,102,241', '99,102,241', '255,195,0'];

  function isMobile(){ return window.innerWidth <= 768; }

  function particleCount(){
    var area = window.innerWidth * window.innerHeight;
    var base = Math.round(area / 16000); // 密度
    if (isMobile()) base = Math.round(base * 0.5);
    return Math.max(28, Math.min(base, 90));
  }

  function rand(min, max){ return Math.random() * (max - min) + min; }

  function makeParticle(){
    return {
      x: Math.random() * W,
      y: Math.random() * H,
      vx: rand(-0.18, 0.18),
      vy: rand(-0.18, 0.18),
      r: rand(1.1, 2.6),
      c: COLORS[Math.floor(Math.random() * COLORS.length)],
      a: rand(0.35, 0.75)
    };
  }

  function build(){
    W = canvas.clientWidth;
    H = canvas.clientHeight;
    canvas.width = Math.floor(W * dpr);
    canvas.height = Math.floor(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    var n = particleCount();
    particles = [];
    for (var i = 0; i < n; i++) particles.push(makeParticle());
  }

  var LINK_DIST = 128;
  function draw(){
    ctx.clearRect(0, 0, W, H);
    // 连线：邻近粒子间极淡靛蓝线，营造网络质感
    for (var i = 0; i < particles.length; i++) {
      var p = particles[i];
      for (var j = i + 1; j < particles.length; j++) {
        var q = particles[j];
        var dx = p.x - q.x, dy = p.y - q.y;
        var d2 = dx * dx + dy * dy;
        if (d2 < LINK_DIST * LINK_DIST) {
          var alpha = (1 - Math.sqrt(d2) / LINK_DIST) * 0.16;
          ctx.strokeStyle = 'rgba(99,102,241,' + alpha.toFixed(3) + ')';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(q.x, q.y);
          ctx.stroke();
        }
      }
    }
    // 粒子点
    for (var k = 0; k < particles.length; k++) {
      var pt = particles[k];
      ctx.beginPath();
      ctx.fillStyle = 'rgba(' + pt.c + ',' + pt.a.toFixed(2) + ')';
      ctx.arc(pt.x, pt.y, pt.r, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function step(){
    for (var i = 0; i < particles.length; i++) {
      var p = particles[i];
      p.x += p.vx;
      p.y += p.vy;
      if (p.x < -20) p.x = W + 20; else if (p.x > W + 20) p.x = -20;
      if (p.y < -20) p.y = H + 20; else if (p.y > H + 20) p.y = -20;
    }
    draw();
    raf = requestAnimationFrame(step);
  }

  var resizeTimer = null;
  window.addEventListener('resize', function(){
    if (resizeTimer) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(build, 200);
  });

  build();
  if (reduce) {
    draw(); // 尊重减少动效偏好：只画一帧静态粒子
  } else {
    step();
  }
})();
</script>"""


def build_archive_pages():
    """为每一天生成独立的排版网页 output/archive/<date>.html。"""
    if not os.path.isdir(DAILY_DIR):
        return 0
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    files = sorted([f for f in os.listdir(DAILY_DIR) if f.endswith(".json")], reverse=True)
    count = 0
    for f in files[:90]:
        date_str = f.replace(".json", "")
        data = load_json(os.path.join(DAILY_DIR, f))
        if not data:
            continue
        body = build_content_view(data)
        # 归档区里的链接需要用 ../ 前缀回到 output 根
        archive_nav = build_archive_section(current_date=date_str, prefix="../")
        date_display = data.get("date_display", date_str)
        weekday = data.get("weekday", "")
        mode = data.get("mode", "rule")
        mode_text = "DeepSeek AI 精选" if mode == "ai" else "规则筛选"
        header_line = (esc(date_display) + " " + esc(weekday)
                       + ' <span class="mode-badge">' + esc(mode_text) + '</span>')
        back = '<a href="../index.html" class="back-link">← 返回今日日报</a>'
        gen_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        page = render_page(date_display, header_line, body + archive_nav,
                           back_link_html=back, gen_time=gen_time)
        with open(os.path.join(ARCHIVE_DIR, date_str + ".html"), "w", encoding="utf-8") as fh:
            fh.write(page)
        count += 1
    return count


def copy_data_to_output():
    """将 data/ 目录复制到 output/data（保留原始数据可下载，但页面不再直接跳转到它）。"""
    if not os.path.isdir(DATA_DIR):
        return
    dest = os.path.join(OUTPUT_DIR, "data")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(DATA_DIR, dest)
    print("[OK] Copied data/ into output/data")


def main():
    print("Building HTML (digest layout + archive pages)...")

    daily_data = load_json(NEWS_FILE)
    if daily_data is None:
        raise SystemExit("[ERROR] data/news_items.json not found")

    weekly_data = load_json(WEEKLY_FILE)
    has_weekly = weekly_data is not None and weekly_data.get("items")

    date_display = daily_data.get("date_display", "")
    weekday = daily_data.get("weekday", "")
    mode = daily_data.get("mode", "rule")
    mode_text = "DeepSeek AI 精选" if mode == "ai" else "规则筛选"

    daily_view = build_content_view(daily_data)
    weekly_view = build_content_view(weekly_data) if has_weekly else ""
    archive_html = build_archive_section(current_date=daily_data.get("date_short"))

    toggle_html = ""
    switch_script = ""
    if has_weekly:
        toggle_html = "".join([
            '<div class="toggle-bar">',
            '<button id="btn-daily" onclick="switchView(\'daily\')" class="tab active">日报</button>',
            '<button id="btn-weekly" onclick="switchView(\'weekly\')" class="tab">周报</button>',
            '</div>',
        ])
        switch_script = (
            '<script>\n'
            'function switchView(m){\n'
            '  document.getElementById("daily-view").style.display=m==="daily"?"block":"none";\n'
            '  document.getElementById("weekly-view").style.display=m==="weekly"?"block":"none";\n'
            '  document.getElementById("btn-daily").className="tab"+(m==="daily"?" active":"");\n'
            '  document.getElementById("btn-weekly").className="tab"+(m==="weekly"?" active":"");\n'
            '}\n'
            '</script>\n'
        )

    views_html = '<div id="daily-view">' + daily_view + '</div>'
    if has_weekly:
        views_html += '<div id="weekly-view" style="display:none;">' + weekly_view + '</div>'

    gen_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header_line = (esc(date_display) + " " + esc(weekday)
                   + ' <span class="mode-badge">' + esc(mode_text) + '</span>')

    page = render_page(date_display, header_line, views_html + archive_html,
                       toggle_html=toggle_html, switch_script=switch_script, gen_time=gen_time)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(page)

    n_archive = build_archive_pages()
    copy_data_to_output()

    total = daily_data.get("total_items", 0)
    print("[OK] Built! Items: " + str(total) + " | Mode: " + mode
          + " | Archive pages: " + str(n_archive)
          + (" | Weekly on" if has_weekly else ""))


if __name__ == "__main__":
    main()
