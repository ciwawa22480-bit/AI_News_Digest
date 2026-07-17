#!/usr/bin/env python3
"""
build_html.py
将 AI 资讯数据渲染为精美的 HTML 静态网页
"""
import json
import os
from datetime import datetime, timezone, timedelta

def load_news():
    with open('data/news_items.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def get_source_icon(source):
    icons = {
        "github_trending": "trending_up",
        "github_releases": "new_releases",
        "hacker_news": "forum",
        "ai_hot_feed": "local_fire_department",
        "huggingface_papers": "science",
    }
    return icons.get(source, "article")

def get_source_name(source):
    names = {
        "github_trending": "GitHub Trending",
        "github_releases": "版本发布",
        "hacker_news": "Hacker News",
        "ai_hot_feed": "AI 热点",
        "huggingface_papers": "论文速递",
    }
    return names.get(source, source)

def get_source_gradient(source):
    gradients = {
        "github_trending": "from-gray-700 to-gray-900",
        "github_releases": "from-emerald-500 to-teal-600",
        "hacker_news": "from-orange-500 to-red-500",
        "ai_hot_feed": "from-rose-500 to-pink-600",
        "huggingface_papers": "from-yellow-500 to-amber-600",
    }
    return gradients.get(source, "from-blue-500 to-indigo-600")

def get_source_tag_style(source):
    styles = {
        "github_trending": "bg-gray-50 text-gray-700",
        "github_releases": "bg-emerald-50 text-emerald-700",
        "hacker_news": "bg-orange-50 text-orange-700",
        "ai_hot_feed": "bg-rose-50 text-rose-700",
        "huggingface_papers": "bg-amber-50 text-amber-700",
    }
    return styles.get(source, "bg-blue-50 text-blue-700")

def get_importance_badge(importance):
    if importance == "high":
        return '<span class="tag bg-red-50 text-red-600 border border-red-200">\U0001F525 重磅</span>'
    elif importance == "medium":
        return '<span class="tag bg-blue-50 text-blue-600 border border-blue-200">\U0001F4CC 关注</span>'
    else:
        return ''

def build_news_card(item):
    """生成单个新闻卡片"""
    source_icon = get_source_icon(item["source"])
    source_name = get_source_name(item["source"])
    gradient = get_source_gradient(item["source"])
    tag_style = get_source_tag_style(item["source"])
    importance_badge = get_importance_badge(item.get("importance", "medium"))
    
    extra = item.get("extra", {})
    meta_parts = []
    if extra.get("stars"):
        meta_parts.append('<span>\u2B50 ' + str(extra["stars"]) + '</span>')
    if extra.get("today_stars"):
        meta_parts.append('<span>\U0001F4C8 ' + str(extra["today_stars"]) + '</span>')
    if extra.get("score"):
        meta_parts.append('<span>\U0001F53A ' + str(extra["score"]) + ' points</span>')
    if extra.get("comments"):
        meta_parts.append('<span>\U0001F4AC ' + str(extra["comments"]) + '</span>')
    if extra.get("upvotes"):
        meta_parts.append('<span>\U0001F44D ' + str(extra["upvotes"]) + '</span>')
    
    meta_html = " ".join(meta_parts)
    
    links_html = ""
    if item.get("url"):
        links_html += '<a href="' + item["url"] + '" target="_blank" class="text-primary-500 hover:text-primary-700 text-xs font-medium">\u539F\u6587 \u2192</a>'
    if extra.get("hn_url"):
        links_html += ' <a href="' + extra["hn_url"] + '" target="_blank" class="text-orange-500 hover:text-orange-700 text-xs font-medium ml-3">\u8BA8\u8BBA \u2192</a>'
    
    card = '''
            <article class="card-hover bg-white rounded-xl p-5 shadow-sm border border-gray-100">
                <div class="flex items-start gap-4">
                    <div class="w-10 h-10 bg-gradient-to-br ''' + gradient + ''' rounded-lg flex items-center justify-center flex-shrink-0">
                        <span class="material-symbols-outlined text-white text-lg">''' + source_icon + '''</span>
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2 flex-wrap mb-1.5">
                            <h4 class="font-semibold text-gray-900 text-[15px]">''' + item["title"] + '''</h4>
                            ''' + importance_badge + '''
                        </div>
                        <p class="text-gray-600 text-sm leading-relaxed mb-3">''' + item.get("summary", "") + '''</p>
                        <div class="flex items-center gap-4 text-xs text-gray-400 flex-wrap">
                            <span class="''' + tag_style + ''' px-2 py-0.5 rounded-full text-[11px] font-medium">''' + source_name + '''</span>
                            ''' + meta_html + '''
                            ''' + links_html + '''
                        </div>
                    </div>
                </div>
            </article>'''
    return card

def build_section(title, icon, icon_color, items, count):
    """生成一个分类区块"""
    if not items:
        return ""
    
    cards = "\n".join([build_news_card(item) for item in items])
    
    section = '''
        <section class="mb-10">
            <div class="section-title">
                <span class="material-symbols-outlined ''' + icon_color + '''">''' + icon + '''</span>
                <h3>''' + title + '''</h3>
                <span class="text-sm text-gray-400 ml-2">''' + str(count) + ''' \u6761</span>
            </div>
            <div class="grid gap-3">
                ''' + cards + '''
            </div>
        </section>'''
    return section

def main():
    print("\U0001F3D7\uFE0F \u5F00\u59CB\u6784\u5EFA\u7F51\u9875...")
    
    news_data = load_news()
    items = news_data["items"]
    date_display = news_data.get("date_display", datetime.now().strftime("%Y\u5E74%m\u6708%d\u65E5"))
    date_short = news_data.get("date_short", datetime.now().strftime("%Y-%m-%d"))
    
    # 分类
    high_items = [i for i in items if i.get("importance") == "high"]
    medium_items = [i for i in items if i.get("importance") == "medium"]
    low_items = [i for i in items if i.get("importance") == "low"]
    
    # 来源统计
    source_counts = {}
    for item in items:
        src = item["source"]
        source_counts[src] = source_counts.get(src, 0) + 1
    
    # 统计栏
    stats_html = ""
    for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
        sname = get_source_name(source)
        stats_html += '<div class="text-center"><div class="text-2xl font-bold gradient-text">' + str(count) + '</div><div class="text-xs text-gray-500 mt-1">' + sname + '</div></div>'
    
    grid_cols = min(len(source_counts), 5)
    
    # 区块
    high_section = build_section("\U0001F525 \u91CD\u78C5\u6D88\u606F", "whatshot", "text-red-500", high_items, len(high_items))
    medium_section = build_section("\U0001F4CC \u503C\u5F97\u5173\u6CE8", "bookmark", "text-blue-500", medium_items, len(medium_items))
    low_section = build_section("\U0001F4CE \u5176\u4ED6\u52A8\u6001", "list", "text-gray-400", low_items, len(low_items))
    
    gen_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Pulse - ''' + date_short + ''' AI \u8D44\u8BAF\u65E5\u62A5</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700;900&family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet" />
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    fontFamily: { sans: ['Inter', 'Noto Sans SC', 'sans-serif'] },
                    colors: {
                        primary: { 50:'#f0f7ff',100:'#e0efff',200:'#b9dfff',300:'#7cc4ff',400:'#36a5ff',500:'#0b8aff',600:'#006be0',700:'#0054b5' },
                    }
                }
            }
        }
    </script>
    <style>
        body { font-family: 'Inter', 'Noto Sans SC', sans-serif; background: #f8fafc; }
        .glass { background: rgba(255,255,255,0.72); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.4); }
        .gradient-hero { background: linear-gradient(135deg, #0b8aff 0%, #6366f1 40%, #d946ef 100%); }
        .gradient-text { background: linear-gradient(135deg, #0b8aff, #d946ef); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
        .card-hover { transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
        .card-hover:hover { transform: translateY(-3px); box-shadow: 0 16px 32px -8px rgba(0,0,0,0.1); }
        .tag { display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 500; }
        .animate-float { animation: float 6s ease-in-out infinite; }
        @keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
        .section-title { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
        .section-title h3 { font-size: 18px; font-weight: 700; color: #1a1a2e; }
    </style>
</head>
<body class="min-h-screen">
    <header class="gradient-hero relative overflow-hidden">
        <div class="absolute inset-0 opacity-10">
            <div class="absolute top-10 left-10 w-72 h-72 bg-white rounded-full blur-3xl animate-float"></div>
            <div class="absolute bottom-10 right-20 w-96 h-96 bg-purple-200 rounded-full blur-3xl animate-float" style="animation-delay:-3s;"></div>
        </div>
        <nav class="relative z-10 max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="w-9 h-9 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur-sm">
                    <span class="material-symbols-outlined text-white text-lg">hub</span>
                </div>
                <span class="text-white font-bold text-lg">AI Pulse</span>
            </div>
            <a href="https://github.com/ciwawa22480-bit/AI_News_Digest" target="_blank" class="flex items-center gap-1.5 bg-white/15 hover:bg-white/25 backdrop-blur-sm text-white px-3 py-1.5 rounded-lg text-sm font-medium transition">
                <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
                \u6E90\u7801
            </a>
        </nav>
        <div class="relative z-10 max-w-6xl mx-auto px-6 pt-12 pb-20 text-center">
            <div class="inline-flex items-center gap-2 bg-white/15 backdrop-blur-sm rounded-full px-4 py-1.5 mb-5">
                <span class="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
                <span class="text-white/90 text-sm font-medium">\u6BCF\u65E5\u81EA\u52A8\u66F4\u65B0 \u00B7 \u591A\u6E90\u805A\u5408 \u00B7 AI \u6458\u8981</span>
            </div>
            <h1 class="text-4xl md:text-5xl font-black text-white mb-4 leading-tight">AI \u8D44\u8BAF\u65E5\u62A5</h1>
            <p class="text-white/70 text-lg mb-2">''' + date_display + '''</p>
            <p class="text-white/50 text-sm">\u5171 ''' + str(len(items)) + ''' \u6761\u8D44\u8BAF \u00B7 \u6765\u81EA ''' + str(len(source_counts)) + ''' \u4E2A\u4FE1\u6E90 \u00B7 ''' + str(len(high_items)) + ''' \u6761\u91CD\u78C5</p>
        </div>
        <div class="absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-[#f8fafc] to-transparent"></div>
    </header>

    <section class="max-w-6xl mx-auto px-6 -mt-6 relative z-20 mb-10">
        <div class="glass rounded-2xl p-5 shadow-lg grid grid-cols-''' + str(grid_cols) + ''' gap-4">
            ''' + stats_html + '''
        </div>
    </section>

    <main class="max-w-6xl mx-auto px-6 pb-16">
        ''' + high_section + '''
        ''' + medium_section + '''
        ''' + low_section + '''
    </main>

    <footer class="bg-gray-900 text-white py-10">
        <div class="max-w-6xl mx-auto px-6 text-center">
            <div class="flex items-center justify-center gap-2 mb-3">
                <span class="material-symbols-outlined text-primary-400">hub</span>
                <span class="font-bold">AI Pulse</span>
            </div>
            <p class="text-gray-400 text-sm mb-2">GitHub Actions \u81EA\u52A8\u8FD0\u884C \u00B7 \u591A\u6E90\u805A\u5408 \u00B7 AI \u667A\u80FD\u6458\u8981</p>
            <p class="text-gray-500 text-xs">\u6570\u636E\u6765\u6E90\uFF1AGitHub Trending \u00B7 Hacker News \u00B7 AI HOT Feed \u00B7 Hugging Face Papers</p>
            <p class="text-gray-600 text-xs mt-3">\u751F\u6210\u4E8E ''' + gen_time + '''</p>
        </div>
    </footer>
</body>
</html>'''
    
    os.makedirs("output", exist_ok=True)
    with open("output/index.html", 'w', encoding='utf-8') as f:
        f.write(html)
    
    print("\u2705 \u7F51\u9875\u751F\u6210\u5B8C\u6210\uFF01")
    print("   \u8D44\u8BAF\u6570: " + str(news_data['total_items']))
    print("   \u8F93\u51FA: output/index.html")

if __name__ == "__main__":
    main()
