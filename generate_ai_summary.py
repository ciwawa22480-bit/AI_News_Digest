#!/usr/bin/env python3
"""
generate_ai_summary.py - v2 (商业化版)
将抓取的原始数据转化为面向商业决策者的中文资讯摘要
核心改进：
1. 商业价值筛选和评分
2. 要点提取（每条3-5个要点）
3. 本地生活相关性标注
4. 头部汇总生成
5. 周报/月报数据聚合
"""
import json
import os
import re
import sys
import glob
from datetime import datetime, timezone, timedelta

def load_raw_news():
    with open('data/raw_news.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def load_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

SOURCE_NAMES = {
    "github_trending": "GitHub",
    "hacker_news": "技术社区",
    "ai_hot_feed": "AI 热点",
    "huggingface_papers": "前沿论文",
    "github_releases": "版本更新",
    "36kr_ai": "36氪",
    "aibase": "AI 工具",
    "particle_news": "科技资讯",
    "the_rundown_ai": "AI 简报",
    "tldr_ai": "技术速递",
    "product_hunt": "新品发现",
    "toolify": "工具榜单",
    "chatpaper": "论文推荐",
}

# ============ 商业价值评分 ============

def score_business_value(item, config):
    """对每条资讯进行商业价值评分 (0-100)"""
    title = (item.get("title", "") + " " + item.get("description", "")).lower()
    score = 30  # 基础分
    
    biz = config.get("business_focus", {})
    
    # 头部公司提及 +20
    for company in biz.get("top_companies", []):
        if company.lower() in title:
            score += 20
            break
    
    # 商业关键词 +15 each (max 30)
    commercial_hits = 0
    for kw in biz.get("commercial_keywords", []):
        if kw.lower() in title:
            commercial_hits += 1
    score += min(commercial_hits * 15, 30)
    
    # 本地生活关键词 +25
    for kw in biz.get("local_life_keywords", []):
        if kw.lower() in title:
            score += 25
            break
    
    # 有具体数字/金额 +10
    if re.search(r'\$[\d,.]+|[\d,.]+亿|[\d,.]+万|billion|million', title):
        score += 10
    
    return min(score, 100)

def check_local_life_relevance(item, config):
    """检查是否与本地生活商业化相关"""
    text = (item.get("title", "") + " " + item.get("description", "")).lower()
    keywords = config.get("business_focus", {}).get("local_life_keywords", [])
    
    hits = []
    for kw in keywords:
        if kw.lower() in text:
            hits.append(kw)
    
    return len(hits) > 0, hits

def extract_key_points(item):
    """从描述中提取要点"""
    desc = item.get("description", "")
    title = item.get("title", "")
    source = item.get("source", "")
    
    points = []
    
    # 基于来源生成不同风格的要点
    if source == "hacker_news":
        score = item.get("score", 0)
        comments = item.get("comments", 0)
        if score:
            points.append(f"社区热度：{score} 分，{comments} 条讨论")
        points.append("技术社区高度关注的 AI 话题")
        
    elif source in ("huggingface_papers", "chatpaper"):
        if desc:
            # 从摘要中提取前几句
            sentences = re.split(r'[.。!！?？]', desc)
            for s in sentences[:3]:
                s = s.strip()
                if len(s) > 15:
                    points.append(s[:80])
        if not points:
            points.append("AI 前沿研究论文")
    
    elif source == "36kr_ai":
        if desc:
            sentences = re.split(r'[.。!！?？;；]', desc)
            for s in sentences[:3]:
                s = s.strip()
                if len(s) > 8:
                    points.append(s[:80])
        if not points:
            points.append("国内 AI 行业动态报道")
    
    elif source == "product_hunt":
        points.append("新上线的 AI 产品/工具")
        if desc:
            points.append(desc[:80])
    
    elif source == "ai_hot_feed":
        if desc:
            sentences = re.split(r'[.。!！?？;；]', desc)
            for s in sentences[:3]:
                s = s.strip()
                if len(s) > 8:
                    points.append(s[:80])
        if not points:
            points.append("AI 行业热点资讯")
    
    else:
        if desc:
            sentences = re.split(r'[.。!！?？;；]', desc)
            for s in sentences[:2]:
                s = s.strip()
                if len(s) > 8:
                    points.append(s[:80])
    
    # 确保至少有1个要点
    if not points:
        points.append(f"来源：{SOURCE_NAMES.get(source, source)}")
    
    return points[:5]

def determine_category(item, config):
    """判断商业分类"""
    text = (item.get("title", "") + " " + item.get("description", "")).lower()
    
    if any(kw in text for kw in ["发布", "推出", "上线", "launch", "release", "announce"]):
        if any(kw in text for kw in ["模型", "model", "gpt", "llm", "claude"]):
            return "模型发布"
        return "产品动态"
    
    if any(kw in text for kw in ["融资", "收购", "估值", "ipo", "funding", "acquisition", "valuation", "billion", "million"]):
        return "投融资"
    
    if any(kw in text for kw in ["合作", "战略", "partnership", "collaborate", "deal"]):
        return "战略合作"
    
    if any(kw in text for kw in ["广告", "营销", "marketing", "ads", "advertising", "brand"]):
        return "营销广告"
    
    if any(kw in text for kw in ["本地", "外卖", "到店", "零售", "local", "delivery", "retail", "food"]):
        return "本地生活"
    
    if any(kw in text for kw in ["论文", "研究", "paper", "research", "study"]):
        return "前沿研究"
    
    if any(kw in text for kw in ["工具", "tool", "app", "saas", "platform"]):
        return "工具应用"
    
    return "行业动态"

def generate_importance(score):
    """根据商业价值评分确定重要性"""
    if score >= 70:
        return "high"
    elif score >= 45:
        return "medium"
    else:
        return "low"

def generate_executive_summary(items):
    """生成头部执行摘要"""
    high_items = [i for i in items if i.get("importance") == "high"]
    
    summary_points = []
    
    # 按分类聚合
    categories = {}
    for item in high_items[:10]:
        cat = item.get("category", "行业动态")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(item["title"])
    
    for cat, titles in list(categories.items())[:5]:
        summary_points.append(f"【{cat}】{titles[0]}")
    
    # 如果高重要性不够，补充中等重要性
    if len(summary_points) < 3:
        medium_items = [i for i in items if i.get("importance") == "medium"]
        for item in medium_items[:5 - len(summary_points)]:
            summary_points.append(f"【{item.get('category', '动态')}】{item['title']}")
    
    return summary_points[:8]

def generate_fallback_item(item, config):
    """增强版降级摘要 - 面向商业决策者"""
    source = item["source"]
    title = item.get("title", "")
    desc = item.get("description", "")
    
    # 商业价值评分
    biz_score = score_business_value(item, config)
    importance = generate_importance(biz_score)
    
    # 本地生活相关性
    is_local, local_keywords = check_local_life_relevance(item, config)
    
    # 要点提取
    key_points = extract_key_points(item)
    
    # 分类
    category = determine_category(item, config)
    
    # 生成摘要
    if desc and len(desc) > 20:
        summary = desc[:150]
    elif source == "36kr_ai":
        summary = f"36氪报道：{title}。关注国内 AI 产业最新商业动态。"
    elif source == "hacker_news":
        summary = f"技术社区热议：{title}。该话题引发广泛讨论，可能预示行业新趋势。"
    elif source == "ai_hot_feed":
        summary = f"AI 行业热点：{title}。"
    elif source in ("huggingface_papers", "chatpaper"):
        summary = f"前沿研究：{title}。该论文可能对 AI 应用商业化产生影响。"
    elif source == "product_hunt":
        summary = f"新产品上线：{title}。值得关注其商业模式和应用场景。"
    elif source == "toolify":
        summary = f"热门 AI 工具：{title}。观察市场需求和用户偏好变化。"
    else:
        summary = f"{title}。"
    
    # 本地生活标注
    local_life_note = ""
    if is_local:
        local_life_note = f"与本地生活商业化相关：涉及{', '.join(local_keywords[:3])}"
    
    # 展示标题处理
    display_title = title if len(title) <= 40 else title[:37] + "..."
    
    return {
        "title": display_title,
        "summary": summary,
        "key_points": key_points,
        "importance": importance,
        "biz_score": biz_score,
        "category": category,
        "is_local_life": is_local,
        "local_life_note": local_life_note,
        "tags": [category],
        "source": source,
        "original_title": title,
        "url": item.get("url", ""),
        "extra": {
            "stars": item.get("stars"),
            "score": item.get("score"),
            "comments": item.get("comments"),
            "upvotes": item.get("upvotes"),
            "today_stars": item.get("today_stars"),
            "hn_url": item.get("hn_url"),
        }
    }

def generate_with_openai(items, config):
    """使用 OpenAI API 生成商业化摘要"""
    from openai import OpenAI
    
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    news_items = []
    
    biz = config.get("business_focus", {})
    top_companies = ", ".join(biz.get("top_companies", [])[:10])
    local_keywords = ", ".join(biz.get("local_life_keywords", [])[:10])
    
    source_groups = {}
    for item in items:
        src = item["source"]
        if src not in source_groups:
            source_groups[src] = []
        source_groups[src].append(item)
    
    for source, group_items in source_groups.items():
        batch = group_items[:15]
        
        items_text = ""
        for i, item in enumerate(batch, 1):
            items_text += f"\n{i}. {item['title']}"
            if item.get("description"):
                items_text += f"\n   {item['description'][:250]}"
            if item.get("url"):
                items_text += f"\n   URL: {item['url']}"
        
        prompt = f"""你是一个面向商业决策者的 AI 行业分析师。你的读者是本地生活商业化部门的人员，他们关注：
1. 头部互联网公司和 AI 公司的商业动作（{top_companies}等）
2. AI 如何改变广告、营销、本地生活、到店、外卖等商业场景
3. 值得借鉴的外部玩家玩法和商业模式

请分析以下资讯，为每条生成商业化视角的摘要：
{items_text}

输出 JSON 数组格式：
[
  {{
    "title": "20-35字中文标题，突出商业价值",
    "summary": "80-150字摘要：这是什么、商业价值在哪、对行业意味什么",
    "key_points": ["要点1(20字内)", "要点2", "要点3"],
    "importance": "high/medium/low (商业价值判断)",
    "category": "产品动态/投融资/战略合作/模型发布/营销广告/本地生活/前沿研究/工具应用/行业动态",
    "is_local_life": true/false,
    "local_life_note": "如果与本地生活相关，说明相关性(30字内)，否则空字符串"
  }}
]

判断标准：
- importance=high: 头部公司重大动作、大额融资、颠覆性产品、直接影响本地生活
- importance=medium: 值得关注的趋势、中型公司动态、有参考价值的玩法
- importance=low: 一般工具更新、学术论文（无明确商业应用）
- 如果条目与 AI 商业化完全无关（纯技术讨论），可以标记 importance=low
- 涉及本地生活相关词汇({local_keywords})时 is_local_life=true"""

        try:
            response = client.chat.completions.create(
                model=os.environ.get("AI_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=4000
            )
            result_text = response.choices[0].message.content.strip()
            
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1].rsplit("```", 1)[0]
            
            summaries = json.loads(result_text)
            
            for i, summary in enumerate(summaries):
                if i < len(batch):
                    news_items.append({
                        **summary,
                        "biz_score": score_business_value(batch[i], config),
                        "source": source,
                        "original_title": batch[i]["title"],
                        "url": batch[i].get("url", ""),
                        "extra": {
                            "stars": batch[i].get("stars"),
                            "score": batch[i].get("score"),
                            "comments": batch[i].get("comments"),
                            "upvotes": batch[i].get("upvotes"),
                            "today_stars": batch[i].get("today_stars"),
                            "hn_url": batch[i].get("hn_url"),
                        }
                    })
            
            print(f"  [OK] [{SOURCE_NAMES.get(source, source)}] {len(summaries)} items")
            
        except Exception as e:
            print(f"  [WARN] [{source}] AI failed: {e}, using fallback")
            for item in batch:
                news_items.append(generate_fallback_item(item, config))
    
    return news_items

def load_weekly_data():
    """加载本周历史数据用于周报"""
    weekly_items = []
    today = datetime.now(timezone(timedelta(hours=8)))
    
    # 找到本周一
    weekday = today.weekday()
    monday = today - timedelta(days=weekday)
    
    for i in range(7):
        day = monday + timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        filepath = f"data/daily/{day_str}.json"
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    day_data = json.load(f)
                    weekly_items.extend(day_data.get("items", []))
            except:
                pass
    
    return weekly_items

def main():
    config = load_config()
    raw_data = load_raw_news()
    items = raw_data["items"]
    
    print("=" * 60)
    print("AI Commercial News Summary - Start")
    print(f"   Items: {len(items)}")
    print("=" * 60)
    
    # 生成摘要
    if os.environ.get("OPENAI_API_KEY"):
        print("  [KEY] Using AI mode")
        news_items = generate_with_openai(items, config)
    else:
        print("  [INFO] Using rule-based mode (no API key)")
        news_items = []
        for item in items:
            news_items.append(generate_fallback_item(item, config))
    
    # 按商业价值排序
    news_items.sort(key=lambda x: x.get("biz_score", 0), reverse=True)
    
    # 生成执行摘要
    exec_summary = generate_executive_summary(news_items)
    
    # 统计
    beijing_tz = timezone(timedelta(hours=8))
    now_beijing = datetime.now(beijing_tz)
    
    # 保存当天数据到 daily 目录
    os.makedirs("data/daily", exist_ok=True)
    today_str = now_beijing.strftime("%Y-%m-%d")
    
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date_display": now_beijing.strftime("%Y\u5e74%m\u6708%d\u65e5"),
        "date_short": today_str,
        "weekday": now_beijing.strftime("%A"),
        "total_items": len(news_items),
        "high_count": len([i for i in news_items if i.get("importance") == "high"]),
        "local_life_count": len([i for i in news_items if i.get("is_local_life")]),
        "sources_count": len(set(i["source"] for i in news_items)),
        "executive_summary": exec_summary,
        "categories": list(set(i.get("category", "") for i in news_items)),
        "items": news_items
    }
    
    # 保存主文件
    with open("data/news_items.json", 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    # 保存日度存档
    with open(f"data/daily/{today_str}.json", 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    # 生成周报数据
    weekly_items = load_weekly_data()
    if weekly_items:
        # 去重
        seen_titles = set()
        unique_weekly = []
        for item in weekly_items:
            t = item.get("original_title", item.get("title", ""))
            if t not in seen_titles:
                seen_titles.add(t)
                unique_weekly.append(item)
        
        unique_weekly.sort(key=lambda x: x.get("biz_score", 0), reverse=True)
        weekly_summary = generate_executive_summary(unique_weekly)
        
        week_start = (now_beijing - timedelta(days=now_beijing.weekday())).strftime("%m.%d")
        week_end = now_beijing.strftime("%m.%d")
        
        weekly_output = {
            "week_range": f"{week_start}-{week_end}",
            "total_items": len(unique_weekly),
            "high_count": len([i for i in unique_weekly if i.get("importance") == "high"]),
            "executive_summary": weekly_summary,
            "items": unique_weekly
        }
        
        with open("data/weekly_items.json", 'w', encoding='utf-8') as f:
            json.dump(weekly_output, f, ensure_ascii=False, indent=2)
    
    print()
    print("=" * 60)
    print(f"Done! Total: {len(news_items)} | High: {output['high_count']} | Local Life: {output['local_life_count']}")
    print(f"   Saved: data/news_items.json + data/daily/{today_str}.json")
    print("=" * 60)

if __name__ == "__main__":
    main()
