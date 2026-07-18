#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_html.py

将 AI 精选后的资讯数据渲染为简洁的静态网页。
风格对标「AI日报沉淀」：

- 按分类（大厂动向 / 初创动向 / 生态动向 / 观点与深度）分区展示
- 每条资讯：标题 + 一句话说明 + 影响等级 + fact/观点标注 + 来源链接
- 日报 / 周报可切换
- 简洁清爽的列表式布局（非繁重卡片）
- 底部月度存档
"""
import os
import json
import html
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DAILY_DIR = os.path.join(DATA_DIR, "daily")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

NEWS_FILE = os.path.join(DATA_DIR, "news_items.json")
WEEKLY_FILE = os.path.join(DATA_DIR, "weekly_items.json")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")


# 分类图标和颜色
CATEGORY_CONFIG = {
    "大厂动向": {"icon": "apartment", "color": "#4f46e5", "bg": "#eef2ff", "border": "#c7d2fe"},
    "初创动向": {"icon": "rocket_launch", "color": "#059669", "bg": "#ecfdf5", "border": "#a7f3d0"},
    "生态动向": {"icon": "public", "color": "#d97706", "bg": "#fffbeb", "border": "#fde68a"},
    "观点与深度": {"icon": "psychology", "color": "#7c3aed", "bg": "#f5f3ff", "border": "#ddd6fe"},
}

# 分类展示顺序
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


def build_item_row(item):
    """构建单条资讯行。"""
    title = item.get("title", "")
    summary = item.get("summary", "")
    impact = item.get("impact", "medium")
    item_type = item.get("type", "fact")
    source = item.get("source", "")
    url = item.get("url", "")
    local_hint = item.get("local_life_hint", "")

    # 影响等级标签
    if impact == "high":
        impact_html = '<span class="impact-high">高影响</span>'
    else:
        impact_html = '<span class="impact-medium">中影响</span>'

    # fact/观点 标签
    if item_type == "opinion":
        type_html = '<span class="type-opinion">观点</span>'
    else:
        type_html = '<span class="type-fact">fact</span>'

    # 来源和链接
    source_html = ""
    if url:
        source_html = ('<a href="' + esc(url) + '" target="_blank" rel="noopener" '
                       'class="source-link">' + esc(source) + ' →</a>')
    elif source:
        source_html = '<span class="source-text">' + esc(source) + '</span>'

    # 本地生活启发
    local_html = ""
    if local_hint:
        local_html = ('<div class="local-hint">'
                      '<span class="material-symbols-outlined local-icon">storefront</span>'
                      + esc(local_hint) + '</div>')

    return "".join([
        '<div class="news-item">',
        '<div class="item-header">',
        '<div class="item-badges">',
        impact_html,
        type_html,
        '</div>',
        '<h4 class="item-title">', esc(title), '</h4>',
        '</div>',
        '<p class="item-summary">', esc(summary), '</p>',
        local_html,
        '<div class="item-footer">',
        source_html,
        '</div>',
        '</div>',
    ])


def build_category_section(category, items):
    """构建一个分类区块。"""
    if not items:
        return ""

    cfg = CATEGORY_CONFIG.get(category, CATEGORY_CONFIG["大厂动向"])
    icon = cfg["icon"]
    color = cfg["color"]

    rows = "\n".join([build_item_row(it) for it in items])

    return "".join([
        '<section class="category-section">',
        '<div class="category-header" style="--cat-color: ', color, ';">',
        '<span class="material-symbols-outlined category-icon" style="color: ', color, ';">', icon, '</span>',
        '<h3 class="category-title">', esc(category), '</h3>',
        '<span class="category-count">', str(len(items)), ' 条</span>',
        '</div>',
        '<div class="category-items">',
        rows,
        '</div>',
        '</section>',
    ])


def build_content_view(data):
    """构建一套完整内容区。"""
    if not data or not data.get("items"):
        return ('<div class="empty-state">'
                '<span class="material-symbols-outlined">inbox</span>'
                '<p>暂无数据</p></div>')

    items = data.get("items", [])

    # 按分类分组
    grouped = {}
    for item in items:
        cat = item.get("category", "大厂动向")
        grouped.setdefault(cat, []).append(item)

    sections = ""
    for cat in CATEGORY_ORDER:
        if cat in grouped:
            sections += build_category_section(cat, grouped[cat])

    # 处理不在预定义顺序中的分类
    for cat in grouped:
        if cat not in CATEGORY_ORDER:
            sections += build_category_section(cat, grouped[cat])

    return '<div class="content-area">' + sections + '</div>'


def build_archive_section():
    """底部月度存档。"""
    dates = []
    if os.path.isdir(DAILY_DIR):
        for name in sorted(os.listdir(DAILY_DIR), reverse=True):
            if name.endswith(".json"):
                dates.append(os.path.splitext(name)[0])

    if not dates:
        return ""

    links = ""
    for date_label in dates[:30]:
        links += ('<a href="../data/daily/' + esc(date_label) + '.json" target="_blank" '
                  'class="archive-link">' + esc(date_label) + '</a>')

    return "".join([
        '<section class="archive-section">',
        '<div class="archive-header">',
        '<span class="material-symbols-outlined">calendar_month</span>',
        '<h3>历史存档</h3>',
        '</div>',
        '<div class="archive-links">', links, '</div>',
        '</section>',
    ])


def main():
    print("Building HTML page (AI Daily Digest style)...")

    daily_data = load_json(NEWS_FILE)
    if daily_data is None:
        raise SystemExit("[ERROR] data/news_items.json not found")

    weekly_data = load_json(WEEKLY_FILE)
    has_weekly = weekly_data is not None and weekly_data.get("items")

    date_display = daily_data.get("date_display", datetime.now().strftime("%Y年%m月%d日"))
    weekday = daily_data.get("weekday", "")
    total_items = daily_data.get("total_items", 0)
    high_count = daily_data.get("high_count", 0)
    mode = daily_data.get("mode", "rule")
    gen_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    daily_view = build_content_view(daily_data)
    weekly_view = build_content_view(weekly_data) if has_weekly else ""
    week_range = weekly_data.get("date_display", "") if has_weekly else ""
    archive_html = build_archive_section()

    # 切换按钮
    toggle_html = ""
    if has_weekly:
        toggle_html = "".join([
            '<div class="toggle-wrapper">',
            '<button id="btn-daily" onclick="switchView(\'daily\')" class="toggle-btn active">日报</button>',
            '<button id="btn-weekly" onclick="switchView(\'weekly\')" class="toggle-btn">周报</button>',
            '</div>',
        ])

    switch_script = ""
    if has_weekly:
        switch_script = (
            '<script>\n'
            'function switchView(mode){\n'
            '  var d=document.getElementById("daily-view");\n'
            '  var w=document.getElementById("weekly-view");\n'
            '  var bd=document.getElementById("btn-daily");\n'
            '  var bw=document.getElementById("btn-weekly");\n'
            '  if(mode==="weekly"){\n'
            '    d.style.display="none"; w.style.display="block";\n'
            '    bw.classList.add("active"); bd.classList.remove("active");\n'
            '  }else{\n'
            '    w.style.display="none"; d.style.display="block";\n'
            '    bd.classList.add("active"); bw.classList.remove("active");\n'
            '  }\n'
            '}\n'
            '</script>\n'
        )

    views_html = '<div id="daily-view">' + daily_view + '</div>'
    if has_weekly:
        views_html += '<div id="weekly-view" style="display:none;">' + weekly_view + '</div>'

    mode_label = "AI 精选" if mode == "ai" else "规则筛选"

    html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI 商业日报 · """ + esc(date_display) + """</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet" />
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: "Inter", "Noto Sans SC", -apple-system, sans-serif;
  background: #fafbfc;
  color: #1a1a2e;
  line-height: 1.6;
}
.material-symbols-outlined {
  font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24;
}

/* Header */
.header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 48px 24px 36px;
  text-align: center;
  position: relative;
  overflow: hidden;
}
.header::before {
  content: '';
  position: absolute;
  top: -50%; left: -50%;
  width: 200%; height: 200%;
  background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 60%);
  animation: rotate 20s linear infinite;
}
@keyframes rotate { to { transform: rotate(360deg); } }
.header-content { position: relative; z-index: 1; max-width: 680px; margin: 0 auto; }
.header h1 {
  font-size: 28px; font-weight: 700; color: #fff; margin-bottom: 8px;
}
.header .date {
  font-size: 16px; color: rgba(255,255,255,0.85); margin-bottom: 4px;
}
.header .meta {
  font-size: 13px; color: rgba(255,255,255,0.6);
}
.header .update-badge {
  display: inline-flex; align-items: center; gap: 6px;
  background: rgba(255,255,255,0.15); backdrop-filter: blur(8px);
  border-radius: 20px; padding: 4px 14px; margin-top: 12px;
  font-size: 12px; color: rgba(255,255,255,0.9);
}
.header .update-badge .dot {
  width: 6px; height: 6px; background: #34d399; border-radius: 50%;
  animation: pulse 2s infinite;
}
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }

/* Toggle */
.toggle-wrapper {
  display: flex; justify-content: center; gap: 4px;
  margin-top: 16px;
  background: rgba(255,255,255,0.12); border-radius: 8px;
  padding: 3px; display: inline-flex;
}
.toggle-btn {
  padding: 6px 20px; border: none; border-radius: 6px;
  font-size: 13px; font-weight: 500; cursor: pointer;
  background: transparent; color: rgba(255,255,255,0.7);
  transition: all 0.2s;
}
.toggle-btn.active {
  background: #fff; color: #4f46e5; font-weight: 600;
}

/* Main content */
.container { max-width: 780px; margin: 0 auto; padding: 32px 20px; }

/* Category section */
.category-section { margin-bottom: 32px; }
.category-header {
  display: flex; align-items: center; gap: 8px;
  padding-bottom: 10px; margin-bottom: 16px;
  border-bottom: 2px solid #f1f5f9;
}
.category-icon { font-size: 22px; }
.category-title { font-size: 17px; font-weight: 700; color: #1a1a2e; }
.category-count { font-size: 12px; color: #94a3b8; margin-left: auto; }

/* News item */
.news-item {
  padding: 16px 0;
  border-bottom: 1px solid #f1f5f9;
}
.news-item:last-child { border-bottom: none; }
.item-header { margin-bottom: 6px; }
.item-badges { display: flex; gap: 6px; margin-bottom: 6px; }
.impact-high {
  display: inline-flex; align-items: center; padding: 2px 8px;
  border-radius: 4px; font-size: 11px; font-weight: 600;
  background: #fef2f2; color: #dc2626; border: 1px solid #fecaca;
}
.impact-medium {
  display: inline-flex; align-items: center; padding: 2px 8px;
  border-radius: 4px; font-size: 11px; font-weight: 500;
  background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe;
}
.type-fact {
  display: inline-flex; align-items: center; padding: 2px 8px;
  border-radius: 4px; font-size: 11px; font-weight: 500;
  background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0;
}
.type-opinion {
  display: inline-flex; align-items: center; padding: 2px 8px;
  border-radius: 4px; font-size: 11px; font-weight: 500;
  background: #faf5ff; color: #9333ea; border: 1px solid #e9d5ff;
}
.item-title {
  font-size: 15px; font-weight: 600; color: #1e293b;
  line-height: 1.4;
}
.item-summary {
  font-size: 14px; color: #475569; line-height: 1.6;
  margin-top: 4px;
}
.item-footer {
  margin-top: 8px; display: flex; align-items: center;
}
.source-link {
  font-size: 12px; color: #6366f1; text-decoration: none;
  font-weight: 500; transition: color 0.2s;
}
.source-link:hover { color: #4338ca; }
.source-text { font-size: 12px; color: #94a3b8; }

/* Local life hint */
.local-hint {
  display: flex; align-items: flex-start; gap: 6px;
  margin-top: 8px; padding: 8px 12px;
  background: #f0fdfa; border: 1px solid #ccfbf1;
  border-radius: 6px; font-size: 12px; color: #0f766e;
}
.local-icon { font-size: 16px; color: #14b8a6; flex-shrink: 0; margin-top: 1px; }

/* Archive */
.archive-section {
  margin-top: 40px; padding: 24px;
  background: #f8fafc; border-radius: 12px;
  border: 1px solid #e2e8f0;
}
.archive-header {
  display: flex; align-items: center; gap: 8px; margin-bottom: 12px;
}
.archive-header span { color: #64748b; font-size: 20px; }
.archive-header h3 { font-size: 15px; font-weight: 600; color: #334155; }
.archive-links { display: flex; flex-wrap: wrap; gap: 8px; }
.archive-link {
  padding: 4px 12px; border-radius: 6px; font-size: 12px;
  background: #fff; border: 1px solid #e2e8f0; color: #475569;
  text-decoration: none; transition: all 0.2s;
}
.archive-link:hover { border-color: #6366f1; color: #6366f1; }

/* Footer */
.footer {
  margin-top: 48px; padding: 24px;
  text-align: center; color: #94a3b8; font-size: 12px;
}

/* Empty state */
.empty-state {
  text-align: center; padding: 60px 20px; color: #94a3b8;
}
.empty-state span { font-size: 48px; }
.empty-state p { margin-top: 8px; }

/* Responsive */
@media (max-width: 640px) {
  .header { padding: 36px 16px 28px; }
  .header h1 { font-size: 22px; }
  .container { padding: 20px 16px; }
  .item-title { font-size: 14px; }
  .item-summary { font-size: 13px; }
}
</style>
</head>
<body>

<header class="header">
<div class="header-content">
<h1>AI 商业日报</h1>
<p class="date">""" + esc(date_display) + " " + esc(weekday) + """</p>
<p class="meta">精选 """ + str(total_items) + " 条 · " + str(high_count) + " 条高影响 · " + esc(mode_label) + """</p>
<div class="update-badge">
<span class="dot"></span>
<span>每日自动更新 · 面向本地生活商业化</span>
</div>
""" + toggle_html + """
</div>
</header>

<div class="container">
""" + views_html + """
""" + archive_html + """
</div>

<div class="footer">
<p>由 GitHub Actions 自动生成 · 数据来源：Google News / 36氪 / VentureBeat / The Verge / Hacker News / AI 热点</p>
<p style="margin-top: 4px;">生成于 """ + gen_time + """</p>
</div>

""" + switch_script + """
</body>
</html>"""

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)

    print("[OK] Page built! Items: " + str(total_items)
          + " | Mode: " + mode
          + (" | Weekly enabled" if has_weekly else ""))
    print("   Output: " + os.path.relpath(OUTPUT_FILE, BASE_DIR))


if __name__ == "__main__":
    main()
