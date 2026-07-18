#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_html.py
将 AI 资讯数据渲染为面向商业决策者的中文 HTML 静态网页。

设计目标：
- 头部「本期摘要」区块：展示 executive_summary（5-8 条最重要资讯要点）
- 每条资讯卡片：标题、summary 摘要、key_points 要点列表、分类标签、来源标签
- is_local_life=true 时展示「本地生活相关」徽章与 local_life_note 说明
- 链接按钮统一为「阅读原文」，指向 item["url"]
- 支持日/周切换：若存在 data/weekly_items.json 则展示周报数据
- 统计栏全中文（来源名称映射见 SOURCE_NAMES）
- 底部「月度存档」入口（链接到 data/daily/ 目录下历史文件）
- 风格：渐变紫蓝 Header、白色卡片、Tailwind CDN、Material Symbols、Noto Sans SC

技术约束：
- 纯 Python，不使用外部模板引擎
- 使用 os.path 处理路径
- 采用字符串拼接，避免嵌套 f-string
- 不使用 emoji 字符（改用 Material Symbols 图标或 Unicode 转义）
"""

import os
import json
import html
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# 路径配置（全部基于脚本所在目录，保证在任意 CWD 下都能正确运行）
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DAILY_DIR = os.path.join(DATA_DIR, "daily")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

NEWS_FILE = os.path.join(DATA_DIR, "news_items.json")
WEEKLY_FILE = os.path.join(DATA_DIR, "weekly_items.json")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")


# ---------------------------------------------------------------------------
# 来源 / 分类 映射表
# ---------------------------------------------------------------------------
SOURCE_NAMES = {
    "hacker_news": "技术社区",
    "ai_hot_feed": "AI 热点",
    "huggingface_papers": "前沿论文",
    "36kr_ai": "36氪",
    "aibase": "AI 工具",
    "particle_news": "科技资讯",
    "the_rundown_ai": "AI 简报",
    "tldr_ai": "技术速递",
    "product_hunt": "新品发现",
    "toolify": "工具榜单",
    "chatpaper": "论文推荐",
    # 兼容历史来源
    "github_trending": "GitHub 热门",
    "github_releases": "版本发布",
}

SOURCE_ICONS = {
    "hacker_news": "forum",
    "ai_hot_feed": "local_fire_department",
    "huggingface_papers": "science",
    "36kr_ai": "newspaper",
    "aibase": "apps",
    "particle_news": "language",
    "the_rundown_ai": "mail",
    "tldr_ai": "summarize",
    "product_hunt": "rocket_launch",
    "toolify": "build",
    "chatpaper": "school",
    "github_trending": "trending_up",
    "github_releases": "new_releases",
}

SOURCE_TAG_STYLES = {
    "hacker_news": "bg-orange-50 text-orange-700",
    "ai_hot_feed": "bg-rose-50 text-rose-700",
    "huggingface_papers": "bg-amber-50 text-amber-700",
    "36kr_ai": "bg-blue-50 text-blue-700",
    "aibase": "bg-purple-50 text-purple-700",
    "particle_news": "bg-cyan-50 text-cyan-700",
    "the_rundown_ai": "bg-indigo-50 text-indigo-700",
    "tldr_ai": "bg-teal-50 text-teal-700",
    "product_hunt": "bg-red-50 text-red-700",
    "toolify": "bg-violet-50 text-violet-700",
    "chatpaper": "bg-amber-50 text-amber-700",
    "github_trending": "bg-gray-50 text-gray-700",
    "github_releases": "bg-emerald-50 text-emerald-700",
}

SOURCE_GRADIENTS = {
    "hacker_news": "from-orange-500 to-red-500",
    "ai_hot_feed": "from-rose-500 to-pink-600",
    "huggingface_papers": "from-yellow-500 to-amber-600",
    "36kr_ai": "from-blue-500 to-blue-700",
    "aibase": "from-purple-500 to-purple-700",
    "particle_news": "from-cyan-500 to-cyan-700",
    "the_rundown_ai": "from-indigo-500 to-indigo-700",
    "tldr_ai": "from-teal-500 to-teal-700",
    "product_hunt": "from-red-400 to-orange-500",
    "toolify": "from-violet-500 to-violet-700",
    "chatpaper": "from-amber-500 to-amber-700",
    "github_trending": "from-gray-700 to-gray-900",
    "github_releases": "from-emerald-500 to-teal-600",
}

CATEGORY_STYLES = {
    "产品动态": "bg-orange-50 text-orange-600",
    "产品发布": "bg-orange-50 text-orange-600",
    "模型发布": "bg-purple-50 text-purple-600",
    "投融资": "bg-pink-50 text-pink-600",
    "融资消息": "bg-pink-50 text-pink-600",
    "工具框架": "bg-green-50 text-green-600",
    "开源项目": "bg-gray-50 text-gray-600",
    "论文研究": "bg-yellow-50 text-yellow-700",
    "行业动态": "bg-blue-50 text-blue-600",
    "政策监管": "bg-red-50 text-red-600",
    "AI应用": "bg-indigo-50 text-indigo-600",
    "商业落地": "bg-cyan-50 text-cyan-600",
}


# ---------------------------------------------------------------------------
# 小工具函数
# ---------------------------------------------------------------------------
def esc(text):
    """HTML 转义，避免特殊字符破坏结构。"""
    if text is None:
        return ""
    return html.escape(str(text))


def source_name_cn(source):
    return SOURCE_NAMES.get(source, source or "其他来源")


def source_icon(source):
    return SOURCE_ICONS.get(source, "article")


def source_tag_style(source):
    return SOURCE_TAG_STYLES.get(source, "bg-slate-50 text-slate-700")


def source_gradient(source):
    return SOURCE_GRADIENTS.get(source, "from-indigo-500 to-purple-600")


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 组件构建函数
# ---------------------------------------------------------------------------
def build_importance_badge(importance):
    if importance == "high":
        return ('<span class="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full '
                'text-[11px] font-semibold bg-red-50 text-red-600 border border-red-200">'
                '<span class="material-symbols-outlined text-[13px] leading-none">whatshot</span>重磅</span>')
    if importance == "medium":
        return ('<span class="inline-flex items-center px-2 py-0.5 rounded-full '
                'text-[11px] font-medium bg-blue-50 text-blue-600 border border-blue-200">关注</span>')
    return ""


def build_category_badge(category):
    if not category:
        return ""
    style = CATEGORY_STYLES.get(category, "bg-slate-50 text-slate-600")
    return ('<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium '
            + style + '">' + esc(category) + '</span>')


def build_biz_score_badge(score):
    """商业价值评分小徽章。"""
    if score is None or score == "":
        return ""
    try:
        val = int(score)
    except (ValueError, TypeError):
        return ""
    if val >= 80:
        color = "bg-emerald-50 text-emerald-700 border-emerald-200"
    elif val >= 60:
        color = "bg-amber-50 text-amber-700 border-amber-200"
    else:
        color = "bg-slate-50 text-slate-500 border-slate-200"
    return ('<span class="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[11px] '
            'font-medium border ' + color + '" title="商业价值评分">'
            '<span class="material-symbols-outlined text-[13px] leading-none">insights</span>商业价值 '
            + str(val) + '</span>')


def build_local_life_badge(item):
    """本地生活相关徽章 + 说明。"""
    if not item.get("is_local_life"):
        return ""
    note = item.get("local_life_note", "")
    badge = ('<div class="mt-3 flex items-start gap-2 rounded-lg bg-teal-50 border border-teal-100 px-3 py-2">'
             '<span class="material-symbols-outlined text-teal-600 text-[18px] leading-none mt-0.5">storefront</span>'
             '<div class="text-[12px] leading-relaxed">'
             '<span class="font-semibold text-teal-700">本地生活相关</span>')
    if note:
        badge += '<span class="text-teal-700/80"> · ' + esc(note) + '</span>'
    badge += '</div></div>'
    return badge


def build_key_points(key_points):
    """要点列表。"""
    if not key_points:
        return ""
    lis = ""
    for point in key_points:
        if not point:
            continue
        lis += ('<li class="flex items-start gap-2">'
                '<span class="material-symbols-outlined text-primary-500 text-[16px] leading-none mt-0.5 flex-shrink-0">'
                'arrow_right</span>'
                '<span>' + esc(point) + '</span></li>')
    if not lis:
        return ""
    return ('<ul class="mt-3 space-y-1.5 text-[13px] text-gray-600 leading-relaxed '
            'bg-gray-50/70 rounded-lg px-3 py-2.5 border border-gray-100">' + lis + '</ul>')


def build_news_card(item):
    """生成单条资讯卡片。"""
    source = item.get("source", "")
    src_name = source_name_cn(source)
    src_icon = source_icon(source)
    src_tag = source_tag_style(source)
    gradient = source_gradient(source)

    importance_badge = build_importance_badge(item.get("importance", "medium"))
    category_badge = build_category_badge(item.get("category", ""))
    biz_badge = build_biz_score_badge(item.get("biz_score"))
    key_points_html = build_key_points(item.get("key_points"))
    local_life_html = build_local_life_badge(item)

    summary_text = item.get("summary") or item.get("description") or ""
    title = item.get("title", "（无标题）")
    url = item.get("url", "")

    # 阅读原文按钮（统一文案）
    read_button = ""
    if url:
        read_button = ('<a href="' + esc(url) + '" target="_blank" rel="noopener" '
                       'class="inline-flex items-center gap-1 text-primary-600 hover:text-primary-800 '
                       'text-[13px] font-medium transition">阅读原文'
                       '<span class="material-symbols-outlined text-[16px] leading-none">north_east</span></a>')

    card = ''.join([
        '<article class="card-hover bg-white rounded-xl p-5 shadow-sm border border-gray-100">',
        '<div class="flex items-start gap-4">',
        '<div class="w-10 h-10 bg-gradient-to-br ', gradient,
        ' rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">',
        '<span class="material-symbols-outlined text-white text-[20px]">', src_icon, '</span>',
        '</div>',
        '<div class="flex-1 min-w-0">',
        '<div class="flex items-center gap-2 flex-wrap mb-2">',
        '<h4 class="font-semibold text-gray-900 text-[15px] leading-snug">', esc(title), '</h4>',
        importance_badge,
        '</div>',
        '<p class="text-gray-600 text-[13.5px] leading-relaxed">', esc(summary_text), '</p>',
        key_points_html,
        local_life_html,
        '<div class="flex items-center gap-2 text-xs text-gray-400 flex-wrap mt-3 pt-3 border-t border-gray-50">',
        '<span class="', src_tag, ' px-2 py-0.5 rounded-full text-[11px] font-medium">', esc(src_name), '</span>',
        category_badge,
        biz_badge,
        '<span class="flex-1"></span>',
        read_button,
        '</div>',
        '</div>',
        '</div>',
        '</article>',
    ])
    return card


def build_executive_summary(summary_list):
    """本期摘要区块。"""
    if not summary_list:
        return ""
    rows = ""
    for idx, line in enumerate(summary_list, start=1):
        if not line:
            continue
        rows += ''.join([
            '<li class="flex items-start gap-3">',
            '<span class="flex-shrink-0 w-6 h-6 rounded-full bg-white/25 text-white text-[12px] '
            'font-bold flex items-center justify-center mt-0.5">', str(idx), '</span>',
            '<span class="text-white/95 text-[14px] leading-relaxed">', esc(line), '</span>',
            '</li>',
        ])
    if not rows:
        return ""
    return ''.join([
        '<section class="max-w-6xl mx-auto px-6 -mt-10 relative z-20 mb-8">',
        '<div class="summary-card rounded-2xl p-6 shadow-xl">',
        '<div class="flex items-center gap-2 mb-4">',
        '<span class="material-symbols-outlined text-white text-[22px]">bolt</span>',
        '<h2 class="text-white font-bold text-lg">本期摘要</h2>',
        '<span class="text-white/60 text-xs ml-1">决策者速览</span>',
        '</div>',
        '<ul class="grid gap-3 sm:grid-cols-2">', rows, '</ul>',
        '</div>',
        '</section>',
    ])


def build_stats_bar(items):
    """来源统计栏（全中文）。"""
    source_counts = {}
    for item in items:
        src = item.get("source", "")
        source_counts[src] = source_counts.get(src, 0) + 1

    if not source_counts:
        return "", 3

    stats_html = ""
    for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
        stats_html += ''.join([
            '<div class="text-center">',
            '<div class="text-2xl font-bold gradient-text">', str(count), '</div>',
            '<div class="text-xs text-gray-500 mt-1">', esc(source_name_cn(source)), '</div>',
            '</div>',
        ])
    grid_cols = min(max(len(source_counts), 1), 6)
    wrapper = ''.join([
        '<section class="max-w-6xl mx-auto px-6 mb-10">',
        '<div class="glass rounded-2xl p-5 shadow-lg">',
        '<div class="grid grid-cols-3 sm:grid-cols-', str(grid_cols), ' gap-4">',
        stats_html,
        '</div>',
        '</div>',
        '</section>',
    ])
    return wrapper, grid_cols


def build_cards_section(items):
    """按重要性分组渲染卡片区块。"""
    high_items = [i for i in items if i.get("importance") == "high"]
    medium_items = [i for i in items if i.get("importance") == "medium"]
    low_items = [i for i in items if i.get("importance") not in ("high", "medium")]

    def section(title, icon, icon_color, group):
        if not group:
            return ""
        cards = "\n".join([build_news_card(it) for it in group])
        return ''.join([
            '<section class="mb-10">',
            '<div class="section-title">',
            '<span class="material-symbols-outlined ', icon_color, '">', icon, '</span>',
            '<h3>', title, '</h3>',
            '<span class="text-sm text-gray-400 ml-2">', str(len(group)), ' 条</span>',
            '</div>',
            '<div class="grid gap-3">', cards, '</div>',
            '</section>',
        ])

    parts = [
        section("重磅消息", "whatshot", "text-red-500", high_items),
        section("值得关注", "bookmark", "text-blue-500", medium_items),
        section("其他动态", "list", "text-gray-400", low_items),
    ]
    return "".join(parts)


def build_view(data):
    """构建一个数据集（日报或周报）的完整内容区（摘要 + 统计 + 卡片）。"""
    if not data:
        return ('<div class="max-w-6xl mx-auto px-6 py-16 text-center text-gray-400">'
                '<span class="material-symbols-outlined text-4xl">inbox</span>'
                '<p class="mt-2 text-sm">暂无数据</p></div>')
    items = data.get("items", [])
    summary_html = build_executive_summary(data.get("executive_summary"))
    stats_html, _ = build_stats_bar(items)
    cards_html = build_cards_section(items)
    return ''.join([
        summary_html,
        stats_html,
        '<main class="max-w-6xl mx-auto px-6 pb-4">',
        cards_html,
        '</main>',
    ])


def build_archive_section():
    """底部月度存档入口，链接到 data/daily/ 下的历史文件。"""
    entries = []
    if os.path.isdir(DAILY_DIR):
        for name in sorted(os.listdir(DAILY_DIR), reverse=True):
            if name.endswith(".json") or name.endswith(".html"):
                entries.append(name)

    if entries:
        links = ""
        for name in entries[:60]:
            label = os.path.splitext(name)[0]
            href = "../data/daily/" + name
            links += ''.join([
                '<a href="', esc(href), '" target="_blank" rel="noopener" ',
                'class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/10 ',
                'hover:bg-white/20 text-white/90 text-[13px] transition">',
                '<span class="material-symbols-outlined text-[16px] leading-none">description</span>',
                esc(label), '</a>',
            ])
        body = '<div class="flex flex-wrap justify-center gap-2 mt-4">' + links + '</div>'
    else:
        body = ('<p class="text-gray-500 text-xs mt-3">'
                '历史存档将保存在 data/daily/ 目录，随每日运行自动积累。</p>')

    return ''.join([
        '<section class="max-w-6xl mx-auto px-6 pb-10">',
        '<div class="rounded-2xl bg-gray-800 p-6 text-center">',
        '<div class="flex items-center justify-center gap-2 mb-1">',
        '<span class="material-symbols-outlined text-primary-300">calendar_month</span>',
        '<h3 class="text-white font-bold text-base">月度存档</h3>',
        '</div>',
        '<p class="text-gray-400 text-xs">按日期回溯历次 AI 资讯日报</p>',
        body,
        '</div>',
        '</section>',
    ])


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    print("Building HTML page...")

    daily_data = load_json(NEWS_FILE)
    if daily_data is None:
        raise SystemExit("[ERROR] 未找到 data/news_items.json")

    weekly_data = load_json(WEEKLY_FILE)
    has_weekly = weekly_data is not None

    daily_items = daily_data.get("items", [])
    date_display = daily_data.get("date_display", datetime.now().strftime("%Y\u5e74%m\u6708%d\u65e5"))
    date_short = daily_data.get("date_short", datetime.now().strftime("%Y-%m-%d"))
    total_items = daily_data.get("total_items", len(daily_items))
    high_count = daily_data.get("high_count", len([i for i in daily_items if i.get("importance") == "high"]))

    source_set = set(i.get("source", "") for i in daily_items)
    source_count = daily_data.get("sources_count", len(source_set))

    gen_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # 日报 / 周报视图内容
    daily_view = build_view(daily_data)
    weekly_view = build_view(weekly_data) if has_weekly else ""

    # 头部副标题（周报显示周范围）
    week_range = weekly_data.get("week_range", "") if has_weekly else ""

    # 日/周切换按钮
    toggle_html = ""
    if has_weekly:
        toggle_html = ''.join([
            '<div class="relative z-10 max-w-6xl mx-auto px-6 pb-2 flex justify-center">',
            '<div class="inline-flex bg-white/15 backdrop-blur-sm rounded-full p-1">',
            '<button id="btn-daily" onclick="switchView(\'daily\')" ',
            'class="view-btn view-btn-active px-5 py-1.5 rounded-full text-sm font-medium transition">日报</button>',
            '<button id="btn-weekly" onclick="switchView(\'weekly\')" ',
            'class="view-btn px-5 py-1.5 rounded-full text-sm font-medium transition">周报</button>',
            '</div>',
            '</div>',
        ])

    archive_html = build_archive_section()

    # 数据来源列表（footer）
    footer_sources = " | ".join([source_name_cn(s) for s in source_set if s])

    # JS 切换逻辑
    switch_script = ""
    if has_weekly:
        switch_script = (
            '<script>\n'
            'function switchView(mode){\n'
            '  var d=document.getElementById("view-daily");\n'
            '  var w=document.getElementById("view-weekly");\n'
            '  var bd=document.getElementById("btn-daily");\n'
            '  var bw=document.getElementById("btn-weekly");\n'
            '  if(mode==="weekly"){\n'
            '    d.style.display="none"; w.style.display="block";\n'
            '    bw.classList.add("view-btn-active"); bd.classList.remove("view-btn-active");\n'
            '  }else{\n'
            '    w.style.display="none"; d.style.display="block";\n'
            '    bd.classList.add("view-btn-active"); bw.classList.remove("view-btn-active");\n'
            '  }\n'
            '  window.scrollTo({top:0,behavior:"smooth"});\n'
            '}\n'
            '</script>\n'
        )

    # 组装两个视图容器
    views_html = ('<div id="view-daily">' + daily_view + '</div>')
    if has_weekly:
        views_html += '<div id="view-weekly" style="display:none;">' + weekly_view + '</div>'

    subtitle = date_display
    meta_line = ('共 ' + str(total_items) + ' 条资讯 · 来自 ' + str(source_count)
                 + ' 个信源 · ' + str(high_count) + ' 条重磅')

    # -----------------------------------------------------------------------
    # 拼装最终 HTML
    # -----------------------------------------------------------------------
    head = ''.join([
        '<!DOCTYPE html>\n',
        '<html lang="zh-CN">\n',
        '<head>\n',
        '<meta charset="UTF-8">\n',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n',
        '<title>AI 资讯日报 · ', date_short, '</title>\n',
        '<script src="https://cdn.tailwindcss.com"></script>\n',
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700;900&family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">\n',
        '<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet" />\n',
        '<script>\n',
        'tailwind.config = {\n',
        '  theme: {\n',
        '    extend: {\n',
        '      fontFamily: { sans: ["Inter", "Noto Sans SC", "sans-serif"] },\n',
        '      colors: {\n',
        '        primary: { 50:"#f5f3ff",100:"#ede9fe",200:"#ddd6fe",300:"#c4b5fd",400:"#a78bfa",500:"#8b5cf6",600:"#7c3aed",700:"#6d28d9",800:"#5b21b6" }\n',
        '      }\n',
        '    }\n',
        '  }\n',
        '}\n',
        '</script>\n',
        '<style>\n',
        'body { font-family: "Inter", "Noto Sans SC", sans-serif; background: #f8fafc; }\n',
        '.glass { background: rgba(255,255,255,0.72); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.4); }\n',
        '.gradient-hero { background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 45%, #a855f7 100%); }\n',
        '.summary-card { background: linear-gradient(135deg, #6d28d9 0%, #4f46e5 100%); }\n',
        '.gradient-text { background: linear-gradient(135deg, #7c3aed, #4f46e5); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }\n',
        '.card-hover { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }\n',
        '.card-hover:hover { transform: translateY(-3px); box-shadow: 0 16px 32px -8px rgba(79,70,229,0.18); }\n',
        '.animate-float { animation: float 6s ease-in-out infinite; }\n',
        '@keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }\n',
        '.section-title { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }\n',
        '.section-title h3 { font-size: 18px; font-weight: 700; color: #1a1a2e; }\n',
        '.view-btn { color: rgba(255,255,255,0.75); }\n',
        '.view-btn-active { background: #ffffff; color: #6d28d9; }\n',
        '.material-symbols-outlined { font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24; }\n',
        '</style>\n',
        '</head>\n',
    ])

    header = ''.join([
        '<body class="min-h-screen">\n',
        '<header class="gradient-hero relative overflow-hidden">\n',
        '<div class="absolute inset-0 opacity-10">\n',
        '<div class="absolute top-10 left-10 w-72 h-72 bg-white rounded-full blur-3xl animate-float"></div>\n',
        '<div class="absolute bottom-10 right-20 w-96 h-96 bg-purple-200 rounded-full blur-3xl animate-float" style="animation-delay:-3s;"></div>\n',
        '</div>\n',
        '<nav class="relative z-10 max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">\n',
        '<div class="flex items-center gap-3">\n',
        '<div class="w-9 h-9 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur-sm">\n',
        '<span class="material-symbols-outlined text-white text-lg">hub</span>\n',
        '</div>\n',
        '<span class="text-white font-bold text-lg">AI 资讯日报</span>\n',
        '</div>\n',
        '<span class="text-white/70 text-sm">面向商业决策者</span>\n',
        '</nav>\n',
        '<div class="relative z-10 max-w-6xl mx-auto px-6 pt-10 pb-16 text-center">\n',
        '<div class="inline-flex items-center gap-2 bg-white/15 backdrop-blur-sm rounded-full px-4 py-1.5 mb-5">\n',
        '<span class="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>\n',
        '<span class="text-white/90 text-sm font-medium">每日自动更新 · 多源聚合 · AI 摘要</span>\n',
        '</div>\n',
        '<h1 class="text-4xl md:text-5xl font-black text-white mb-4 leading-tight">AI 资讯日报</h1>\n',
        '<p class="text-white/70 text-lg mb-2">', esc(subtitle),
        ('（周报 ' + esc(week_range) + '）' if week_range else ''), '</p>\n',
        '<p class="text-white/50 text-sm">', meta_line, '</p>\n',
        '</div>\n',
        toggle_html,
        '<div class="pb-6"></div>\n',
        '</header>\n',
    ])

    footer = ''.join([
        archive_html,
        '<footer class="bg-gray-900 text-white py-10">\n',
        '<div class="max-w-6xl mx-auto px-6 text-center">\n',
        '<div class="flex items-center justify-center gap-2 mb-3">\n',
        '<span class="material-symbols-outlined text-primary-300">hub</span>\n',
        '<span class="font-bold">AI 资讯日报</span>\n',
        '</div>\n',
        '<p class="text-gray-400 text-sm mb-2">GitHub Actions 自动运行 · 多源聚合 · AI 智能摘要</p>\n',
        '<p class="text-gray-500 text-xs">数据来源：', esc(footer_sources), '</p>\n',
        '<p class="text-gray-600 text-xs mt-3">生成于 ', gen_time, '</p>\n',
        '</div>\n',
        '</footer>\n',
        switch_script,
        '</body>\n',
        '</html>\n',
    ])

    html_content = head + header + views_html + footer

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)

    print("[OK] Page built! Daily items: " + str(total_items)
          + (" | Weekly enabled" if has_weekly else " | Weekly not found"))
    print("   Output: " + os.path.relpath(OUTPUT_FILE, BASE_DIR))


if __name__ == "__main__":
    main()
