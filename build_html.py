#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_html.py

将 AI 精选资讯渲染为类似「AI日报沉淀」的表格式静态网页。

布局特点：
- 顶部：日期 + 每日编辑一句话总结
- 信号说明：红=高影响 / 黄=中影响 / 灰=信息流
- 主体：按分类分区，每区为表格布局
  - 左列：类型(fact/观点) + 分类名
  - 右列：条目列表，每条含标题+说明+分析子要点
- 日报/周报切换
- 底部：日期归档（按日+按周分组）
"""
import os
import json
import html
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DAILY_DIR = os.path.join(DATA_DIR, "daily")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

NEWS_FILE = os.path.join(DATA_DIR, "news_items.json")
WEEKLY_FILE = os.path.join(DATA_DIR, "weekly_items.json")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")

CATEGORY_ORDER = ["大厂动向", "初创动向", "生态动向", "观点与深度"]


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


def build_item_html(item):
    """单条资讯 HTML。"""
    title = item.get("title", "")
    explanation = item.get("explanation", item.get("summary", ""))
    analysis_points = item.get("analysis_points", [])
    impact = item.get("impact", "medium")
    source = item.get("source", "")
    url = item.get("url", "")
    local_hint = item.get("local_life_hint", "")

    # 标题链接
    if url:
        title_html = '<a href="' + esc(url) + '" target="_blank" class="item-link">' + esc(title) + '</a>'
    else:
        title_html = '<span class="item-title-text">' + esc(title) + '</span>'

    # 说明
    exp_html = ""
    if explanation:
        exp_html = '<span class="item-explanation">：' + esc(explanation) + '</span>'

    # 分析子要点
    points_html = ""
    if analysis_points:
        pts = ""
        for pt in analysis_points[:3]:
            if pt:
                pts += '<li>' + esc(pt) + '</li>'
        if pts:
            points_html = '<ul class="analysis-points">' + pts + '</ul>'

    # 本地生活提示
    local_html = ""
    if local_hint:
        local_html = '<div class="local-hint"><span class="local-tag">营销启发</span>' + esc(local_hint) + '</div>'

    # 来源
    source_html = ""
    if source:
        source_html = '<span class="item-source">(' + esc(source) + ')</span>'

    return "".join([
        '<div class="news-item">',
        '<div class="item-main">',
        impact_dot(impact),
        title_html,
        source_html,
        exp_html,
        '</div>',
        points_html,
        local_html,
        '</div>',
    ])


def build_category_block(category, type_label, items):
    """构建一个分类行（表格行）。"""
    if not items:
        return ""

    items_html = "\n".join([build_item_html(it) for it in items])

    return "".join([
        '<tr class="category-row">',
        '<td class="col-type"><span class="type-label">', esc(type_label), '</span></td>',
        '<td class="col-category"><span class="cat-label">', esc(category), '</span></td>',
        '<td class="col-content">', items_html, '</td>',
        '</tr>',
    ])


def build_content_view(data):
    """构建完整内容视图。"""
    if not data or not data.get("items"):
        return '<div class="empty">暂无数据</div>'

    items = data.get("items", [])
    editorial = data.get("editorial_summary", "")

    # 编辑总结
    editorial_html = ""
    if editorial:
        editorial_html = '<div class="editorial"><strong>' + esc(editorial) + '</strong></div>'

    # 按分类分组
    grouped = {}
    for item in items:
        cat = item.get("category", "大厂动向")
        grouped.setdefault(cat, []).append(item)

    # 分类到 fact/opinion 类型
    fact_categories = ["大厂动向", "初创动向", "生态动向"]
    opinion_categories = ["观点与深度"]

    rows = ""
    for cat in CATEGORY_ORDER:
        if cat not in grouped:
            continue
        type_label = "偏fact类" if cat in fact_categories else "偏观点类"
        rows += build_category_block(cat, type_label, grouped[cat])

    # 处理额外分类
    for cat in grouped:
        if cat not in CATEGORY_ORDER:
            rows += build_category_block(cat, "偏fact类", grouped[cat])

    # 统计信息
    total = len(items)
    high_count = len([i for i in items if i.get("impact") == "high"])
    stats_html = ('<div class="stats">共 ' + str(total) + ' 条精选 · '
                  + str(high_count) + ' 条高影响</div>')

    return "".join([
        editorial_html,
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
    ])


def build_archive_section():
    """按周分组的归档区。"""
    if not os.path.isdir(DAILY_DIR):
        return ""

    files = sorted([f for f in os.listdir(DAILY_DIR) if f.endswith(".json")], reverse=True)
    if not files:
        return ""

    # 按周分组
    beijing = timezone(timedelta(hours=8))
    weeks = {}
    for f in files[:60]:
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
            # 周度归档链接
            archive_html += '<div class="archive-week"><span class="week-label">' + esc(week_range) + '</span>'
            for d in dates:
                archive_html += ('<a href="../data/daily/' + esc(d) + '.json" target="_blank" '
                                 'class="date-link">' + esc(d.split("-", 1)[1]) + '</a>')  # 只显示 MM-DD
            archive_html += '</div>'
        archive_html += '</div>'

    return "".join([
        '<section class="archive-section">',
        '<h3 class="archive-title">历史归档</h3>',
        archive_html,
        '</section>',
    ])


def main():
    print("Building HTML (digest table layout)...")

    daily_data = load_json(NEWS_FILE)
    if daily_data is None:
        raise SystemExit("[ERROR] data/news_items.json not found")

    weekly_data = load_json(WEEKLY_FILE)
    has_weekly = weekly_data is not None and weekly_data.get("items")

    date_display = daily_data.get("date_display", "")
    weekday = daily_data.get("weekday", "")
    mode = daily_data.get("mode", "rule")

    daily_view = build_content_view(daily_data)
    weekly_view = build_content_view(weekly_data) if has_weekly else ""
    archive_html = build_archive_section()

    toggle_html = ""
    if has_weekly:
        toggle_html = "".join([
            '<div class="toggle-bar">',
            '<button id="btn-daily" onclick="switchView(\'daily\')" class="tab active">日报</button>',
            '<button id="btn-weekly" onclick="switchView(\'weekly\')" class="tab">周报</button>',
            '</div>',
        ])

    switch_script = ""
    if has_weekly:
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
    mode_text = "DeepSeek AI 精选" if mode == "ai" else "规则筛选"

    page = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI 商业日报 · """ + esc(date_display) + """</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: "Noto Sans SC", -apple-system, sans-serif; background: #fff; color: #1a1a1a; line-height: 1.7; font-size: 14px; }

/* Header */
.header { padding: 32px 40px 20px; border-bottom: 1px solid #e5e7eb; }
.header h1 { font-size: 22px; font-weight: 700; color: #111; margin-bottom: 4px; }
.header .date-line { font-size: 14px; color: #666; }
.header .mode-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; background: #f0f9ff; color: #0369a1; margin-left: 8px; }

/* Toggle */
.toggle-bar { padding: 12px 40px 0; display: flex; gap: 0; border-bottom: 1px solid #e5e7eb; }
.tab { padding: 8px 24px; border: none; background: none; font-size: 14px; color: #666; cursor: pointer; border-bottom: 2px solid transparent; font-weight: 500; }
.tab.active { color: #4f46e5; border-bottom-color: #4f46e5; }

/* Content */
.container { max-width: 1100px; margin: 0 auto; padding: 24px 40px; }

/* Editorial */
.editorial { padding: 16px 20px; background: #f8fafc; border-left: 4px solid #4f46e5; border-radius: 0 8px 8px 0; margin-bottom: 20px; font-size: 15px; color: #1e293b; }

/* Signal legend */
.signal-legend { font-size: 12px; color: #64748b; margin-bottom: 8px; display: flex; align-items: center; gap: 4px; }
.stats { font-size: 12px; color: #94a3b8; margin-bottom: 16px; }

/* Dots */
.dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; flex-shrink: 0; }
.dot-high { background: #ef4444; }
.dot-medium { background: #f59e0b; }
.dot-low { background: #cbd5e1; }

/* Table */
.digest-table { width: 100%; border-collapse: collapse; }
.category-row td { padding: 16px 12px; vertical-align: top; border-top: 1px solid #e5e7eb; }
.col-type { width: 70px; text-align: center; }
.col-category { width: 90px; text-align: center; }
.col-content { padding-left: 20px !important; }
.type-label { font-size: 12px; color: #64748b; font-weight: 500; white-space: nowrap; }
.cat-label { font-size: 13px; font-weight: 600; color: #1e293b; white-space: nowrap; }

/* News item */
.news-item { margin-bottom: 18px; }
.news-item:last-child { margin-bottom: 0; }
.item-main { display: flex; flex-wrap: wrap; align-items: flex-start; gap: 4px; }
.item-main .dot { margin-top: 6px; }
.item-link { color: #1e40af; text-decoration: none; font-weight: 600; font-size: 14px; }
.item-link:hover { text-decoration: underline; }
.item-title-text { font-weight: 600; font-size: 14px; color: #1e293b; }
.item-explanation { color: #374151; font-size: 13.5px; }
.item-source { color: #94a3b8; font-size: 11px; }

/* Analysis points */
.analysis-points { margin: 6px 0 0 24px; padding: 0; list-style: disc; }
.analysis-points li { font-size: 13px; color: #4b5563; line-height: 1.6; margin-bottom: 3px; }

/* Local hint */
.local-hint { margin: 6px 0 0 24px; padding: 4px 10px; background: #f0fdfa; border: 1px solid #ccfbf1; border-radius: 4px; font-size: 12px; color: #0f766e; }
.local-tag { font-weight: 600; margin-right: 6px; color: #14b8a6; }

/* Archive */
.archive-section { margin-top: 40px; padding-top: 24px; border-top: 1px solid #e5e7eb; }
.archive-title { font-size: 15px; font-weight: 600; color: #374151; margin-bottom: 12px; }
.archive-month { margin-bottom: 12px; }
.archive-month h4 { font-size: 13px; color: #64748b; margin-bottom: 6px; }
.archive-week { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap; }
.week-label { font-size: 12px; color: #94a3b8; min-width: 80px; }
.date-link { font-size: 12px; color: #6366f1; text-decoration: none; padding: 2px 8px; border-radius: 4px; background: #f5f3ff; }
.date-link:hover { background: #ede9fe; }

/* Footer */
.footer { padding: 24px 40px; text-align: center; color: #94a3b8; font-size: 11px; border-top: 1px solid #f1f5f9; margin-top: 32px; }

/* Empty */
.empty { text-align: center; padding: 60px; color: #94a3b8; }

/* Responsive */
@media (max-width: 768px) {
  .header, .container, .footer { padding-left: 16px; padding-right: 16px; }
  .toggle-bar { padding-left: 16px; }
  .col-type, .col-category { display: none; }
  .col-content { padding-left: 0 !important; }
  .category-row td { padding: 12px 0; }
  .category-row::before { content: attr(data-cat); display: block; font-weight: 600; font-size: 13px; color: #4f46e5; margin-bottom: 8px; }
}
</style>
</head>
<body>

<div class="header">
<h1>AI 商业日报</h1>
<div class="date-line">
""" + esc(date_display) + " " + esc(weekday) + """
<span class="mode-badge">""" + esc(mode_text) + """</span>
</div>
</div>

""" + toggle_html + """

<div class="container">
""" + views_html + """
""" + archive_html + """
</div>

<div class="footer">
每日自动更新 · 数据来源：Google News / 36氪 / TechCrunch / VentureBeat / The Verge / The Rundown / HN / AI热点<br>
生成于 """ + gen_time + """
</div>

""" + switch_script + """
</body>
</html>"""

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(page)

    total = daily_data.get("total_items", 0)
    print("[OK] Built! Items: " + str(total) + " | Mode: " + mode
          + (" | Weekly on" if has_weekly else ""))


if __name__ == "__main__":
    main()
