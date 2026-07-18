#!/usr/bin/env python3
"""
build_html.py
将 AI 资讯数据渲染为精美的中文 HTML 静态网页
- 统计栏全中文
- 链接按钮根据来源区分（项目/原文/论文）
- 内容卡片带分类标签和摘要说明
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
        "36kr_ai": "newspaper",
        "aibase": "apps",
        "particle_news": "language",
        "the_rundown_ai": "mail",
        "tldr_ai": "summarize",
        "product_hunt": "rocket_launch",
        "toolify": "build",
        "chatpaper": "school",
    }
    return icons.get(source, "article")

def get_source_name_cn(source):
    """全中文来源名称"""
    names = {
        "github_trending": "GitHub 热门",
        "github_releases": "版本发布",
        "hacker_news": "技术社区",
        "ai_hot_feed": "AI 热点",
        "huggingface_papers": "论文速递",
        "36kr_ai": "36氪 AI",
        "aibase": "AI 工具",
        "particle_news": "科技资讯",
        "the_rundown_ai": "AI 简报",
        "tldr_ai": "技术速递",
        "product_hunt": "新品发现",
        "toolify": "工具榜单",
        "chatpaper": "论文推荐",
    }
    return names.get(source, source)

def get_source_gradient(source):
    gradients = {
        "github_trending": "from-gray-700 to-gray-900",
        "github_releases": "from-emerald-500 to-teal-600",
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
    }
    return gradients.get(source, "from-blue-500 to-indigo-600")

def get_source_tag_style(source):
    styles = {
        "github_trending": "bg-gray-50 text-gray-700",
        "github_releases": "bg-emerald-50 text-emerald-700",
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
    }
    return styles.get(source, "bg-blue-50 text-blue-700")

def get_link_text(source):
    """根据来源类型返回不同的链接按钮文字"""
    link_texts = {
        "hacker_news": "阅读原文",
        "ai_hot_feed": "阅读原文",
        "huggingface_papers": "查看论文",
        "36kr_ai": "阅读原文",
        "aibase": "查看详情",
        "particle_news": "阅读原文",
        "the_rundown_ai": "阅读原文",
        "tldr_ai": "阅读原文",
        "product_hunt": "查看产品",
        "toolify": "查看工具",
        "chatpaper": "查看论文",
    }
    return link_texts.get(source, "阅读原文")

def get_importance_badge(importance):
    if importance == "high":
        return '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-red-50 text-red-600 border border-red-200">重磅</span>'
    elif importance == "medium":
        return '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-blue-50 text-blue-600 border border-blue-200">关注</span>'
    else:
        return ''

def get_category_badge(category):
    """显示分类标签"""
    if not category:
        return ""
    colors = {
        "模型发布": "bg-purple-50 text-purple-600",
        "工具框架": "bg-green-50 text-green-600",
        "开源项目": "bg-gray-50 text-gray-600",
        "论文研究": "bg-yellow-50 text-yellow-700",
        "行业动态": "bg-blue-50 text-blue-600",
        "融资消息": "bg-pink-50 text-pink-600",
        "AI应用": "bg-indigo-50 text-indigo-600",
        "产品发布": "bg-orange-50 text-orange-600",
    }
    style = colors.get(category, "bg-gray-50 text-gray-600")
    return '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium ' + style + '">' + category + '</span>'

def build_news_card(item):
    """生成单个新闻卡片 - 增强版"""
    source_icon = get_source_icon(item["source"])
    source_name = get_source_name_cn(item["source"])
    gradient = get_source_gradient(item["source"])
    tag_style = get_source_tag_style(item["source"])
    importance_badge = get_importance_badge(item.get("importance", "medium"))
    category_badge = get_category_badge(item.get("category", ""))
    link_text = get_link_text(item["source"])
    
    extra = item.get("extra", {})
    meta_parts = []
    if extra.get("stars"):
        meta_parts.append('<span class="inline-flex items-center gap-0.5"><svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>' + str(extra["stars"]) + '</span>')
    if extra.get("today_stars"):
        meta_parts.append('<span class="text-green-600">+' + str(extra["today_stars"]).replace(" stars today", "").strip() + ' today</span>')
    if extra.get("score"):
        meta_parts.append('<span>' + str(extra["score"]) + ' points</span>')
    if extra.get("comments"):
        meta_parts.append('<span>' + str(extra["comments"]) + ' comments</span>')
    if extra.get("upvotes"):
        meta_parts.append('<span>' + str(extra["upvotes"]) + ' votes</span>')
    
    meta_html = " ".join(meta_parts)
    
    # 链接按钮
    links_html = ""
    if item.get("url"):
        links_html += '<a href="' + item["url"] + '" target="_blank" class="inline-flex items-center gap-1 text-primary-500 hover:text-primary-700 text-xs font-medium transition">' + link_text + ' <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg></a>'
    if extra.get("hn_url"):
        links_html += ' <a href="' + extra["hn_url"] + '" target="_blank" class="inline-flex items-center gap-1 text-orange-500 hover:text-orange-700 text-xs font-medium ml-3 transition">讨论 <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg></a>'
    
    # 摘要文字
    summary_text = item.get("summary", "")
    if not summary_text:
        summary_text = item.get("description", "")
    
    card = '''
            <article class="card-hover bg-white rounded-xl p-5 shadow-sm border border-gray-100">
                <div class="flex items-start gap-4">
                    <div class="w-10 h-10 bg-gradient-to-br ''' + gradient + ''' rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                        <span class="material-symbols-outlined text-white text-lg">''' + source_icon + '''</span>
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2 flex-wrap mb-1.5">
                            <h4 class="font-semibold text-gray-900 text-[15px] leading-snug">''' + item["title"] + '''</h4>
                            ''' + importance_badge + '''
                        </div>
                        <p class="text-gray-600 text-sm leading-relaxed mb-3">''' + summary_text + '''</p>
                        <div class="flex items-center gap-3 text-xs text-gray-400 flex-wrap">
                            <span class="''' + tag_style + ''' px-2 py-0.5 rounded-full text-[11px] font-medium">''' + source_name + '''</span>
                            ''' + category_badge + '''
                            ''' + meta_html + '''
                            <span class="flex-1"></span>
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
                <span class="text-sm text-gray-400 ml-2">''' + str(count) + ''' 条</span>
            </div>
            <div class="grid gap-3">
                ''' + cards + '''
            </div>
        </section>'''
    return section

def main():
    print("Building HTML page...")
    
    news_data = load_news()
    items = news_data["items"]
    date_display = news_data.get("date_display", datetime.now().strftime("%Y\u5e74%m\u6708%d\u65e5"))
    date_short = news_data.get("date_short", datetime.now().strftime("%Y-%m-%d"))
    
    # 分类
    high_items = [i for i in items if i.get("importance") == "high"]
    medium_items = [i for i in items if i.get("importance") == "medium"]
    low_items = [i for i in items if i.get("importance") == "low"]
    
    # 来源统计 - 全中文
    source_counts = {}
    for item in items:
        src = item["source"]
        source_counts[src] = source_counts.get(src, 0) + 1
    
    # 统计栏 - 使用中文名称
    stats_html = ""
    for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
        sname = get_source_name_cn(source)
        stats_html += '<div class="text-center"><div class="text-2xl font-bold gradient-text">' + str(count) + '</div><div class="text-xs text-gray-500 mt-1">' + sname + '</div></div>'
    
    grid_cols = min(len(source_counts), 6)
    
    # 区块
    high_section = build_section("重磅消息", "whatshot", "text-red-500", high_items, len(high_items))
    medium_section = build_section("值得关注", "bookmark", "text-blue-500", medium_items, len(medium_items))
    low_section = build_section("其他动态", "list", "text-gray-400", low_items, len(low_items))
    
    gen_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # 来源列表（footer）
    all_sources = [get_source_name_cn(s) for s in source_counts.keys()]
    footer_sources = " | ".join(all_sources)
    
    html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Pulse - ''' + date_short + ''' AI 资讯日报</title>
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
                GitHub
            </a>
        </nav>
        <div class="relative z-10 max-w-6xl mx-auto px-6 pt-12 pb-20 text-center">
            <div class="inline-flex items-center gap-2 bg-white/15 backdrop-blur-sm rounded-full px-4 py-1.5 mb-5">
                <span class="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
                <span class="text-white/90 text-sm font-medium">每日自动更新 · 多源聚合 · AI 摘要</span>
            </div>
            <h1 class="text-4xl md:text-5xl font-black text-white mb-4 leading-tight">AI 资讯日报</h1>
            <p class="text-white/70 text-lg mb-2">''' + date_display + '''</p>
            <p class="text-white/50 text-sm">共 ''' + str(len(items)) + ''' 条资讯 · 来自 ''' + str(len(source_counts)) + ''' 个信源 · ''' + str(len(high_items)) + ''' 条重磅</p>
        </div>
        <div class="absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-[#f8fafc] to-transparent"></div>
    </header>

    <section class="max-w-6xl mx-auto px-6 -mt-6 relative z-20 mb-10">
        <div class="glass rounded-2xl p-5 shadow-lg">
            <div class="grid grid-cols-3 sm:grid-cols-''' + str(grid_cols) + ''' gap-4">
                ''' + stats_html + '''
            </div>
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
            <p class="text-gray-400 text-sm mb-2">GitHub Actions 自动运行 · 多源聚合 · AI 智能摘要</p>
            <p class="text-gray-500 text-xs">数据来源：''' + footer_sources + '''</p>
            <p class="text-gray-600 text-xs mt-3">生成于 ''' + gen_time + '''</p>
        </div>
    </footer>
</body>
</html>'''
    
    os.makedirs("output", exist_ok=True)
    with open("output/index.html", 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"[OK] Page built! Items: {news_data['total_items']}")
    print(f"   Output: output/index.html")

if __name__ == "__main__":
    main()
