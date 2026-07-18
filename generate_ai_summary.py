#!/usr/bin/env python3
"""
generate_ai_summary.py
使用 OpenAI API 将抓取的原始数据转化为中文资讯摘要
支持降级方案：当无 API Key 时使用规则摘要
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

def load_raw_news():
    with open('data/raw_news.json', 'r', encoding='utf-8') as f:
        return json.load(f)

SOURCE_NAMES = {
    "github_trending": "GitHub 热门项目",
    "hacker_news": "Hacker News 热帖",
    "ai_hot_feed": "AI 中文热点",
    "huggingface_papers": "AI 论文",
    "github_releases": "开源项目新版本",
    "36kr_ai": "36氪 AI",
    "aibase": "AI Base",
    "particle_news": "Particle News",
    "the_rundown_ai": "The Rundown AI",
    "tldr_ai": "TLDR AI",
    "product_hunt": "Product Hunt",
    "toolify": "Toolify 工具榜",
    "chatpaper": "ChatPaper 论文",
}

def generate_with_openai(items):
    """使用 OpenAI API 批量生成中文摘要"""
    from openai import OpenAI
    
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    news_items = []
    
    # 按来源分组处理
    source_groups = {}
    for item in items:
        src = item["source"]
        if src not in source_groups:
            source_groups[src] = []
        source_groups[src].append(item)
    
    for source, group_items in source_groups.items():
        batch = group_items[:20]
        
        items_text = ""
        for i, item in enumerate(batch, 1):
            items_text += f"\n{i}. 标题: {item['title']}\n"
            if item.get("description"):
                items_text += f"   描述: {item['description'][:200]}\n"
            if item.get("url"):
                items_text += f"   链接: {item['url']}\n"
            if item.get("stars"):
                items_text += f"   Stars: {item['stars']}\n"
            if item.get("score"):
                items_text += f"   热度: {item['score']}\n"
        
        prompt = f"""你是一个专业的 AI 行业资讯编辑。请基于以下来自"{SOURCE_NAMES.get(source, source)}"的原始数据，为每条生成精炼的中文资讯条目。

原始数据：
{items_text}

请按以下 JSON 数组格式输出（仅输出 JSON，不要其他内容）：
[
  {{
    "title": "15-25字中文标题，简洁有力，有新闻感",
    "summary": "80-120字中文摘要，介绍这个项目/新闻是什么、有什么特点、为什么值得关注",
    "importance": "high/medium/low",
    "category": "模型发布/工具框架/开源项目/论文研究/行业动态/融资消息/AI应用/产品发布",
    "tags": ["标签1", "标签2"]
  }}
]

要求：
1. 标题必须是中文，有新闻感，不要直接用英文仓库名
2. 摘要要有信息量：这是什么、做什么用的、有什么亮点
3. 过滤掉明显与 AI 无关的内容（返回空数组即可）
4. importance 判断：重大模型/产品发布=high，新功能/论文/热门项目=medium，常规更新=low
5. 保持条目与原始数据顺序一致"""

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
            
            print(f"  [OK] [{SOURCE_NAMES.get(source, source)}] {len(summaries)} summaries")
            
        except Exception as e:
            print(f"  [WARN] [{source}] AI failed: {e}")
            for item in batch:
                news_items.append(generate_fallback_item(item))
    
    return news_items

def generate_fallback_item(item):
    """当 AI API 不可用时的降级摘要 - 增强版"""
    source = item["source"]
    title = item.get("title", "")
    desc = item.get("description", "")
    
    if source == "github_trending":
        # 提取仓库名的后半部分作为项目名
        parts = title.split("/")
        project_name = parts[-1] if len(parts) > 1 else title
        
        if desc:
            summary = f"{project_name} - {desc[:100]}。该项目在 GitHub 上获得广泛关注。"
        else:
            summary = f"GitHub 热门 AI 项目 {project_name}，近期获得大量关注和 Star。"
        
        display_title = f"{project_name}：热门 AI 开源项目"
        category = "开源项目"
        importance = "medium"
        
        # 根据 star 数判断重要性
        stars = item.get("stars", "0")
        try:
            if int(str(stars).replace(",", "")) > 20000:
                importance = "high"
        except:
            pass
            
    elif source == "hacker_news":
        summary = f"Hacker News 社区热议话题。{desc[:80]}" if desc else f"该话题在 Hacker News 上引发技术社区广泛讨论。"
        display_title = title if len(title) <= 35 else title[:32] + "..."
        category = "行业动态"
        importance = "medium"
        score = item.get("score", 0)
        if score and int(score) > 200:
            importance = "high"
            
    elif source == "ai_hot_feed":
        summary = desc[:120] if desc else f"AI 领域热点资讯：{title[:60]}"
        display_title = title if len(title) <= 35 else title[:32] + "..."
        category = "行业动态"
        importance = "medium"
        
    elif source == "huggingface_papers":
        summary = f"最新 AI 研究论文。{desc[:100]}" if desc else f"Hugging Face 推荐的高质量 AI 学术论文。"
        display_title = title if len(title) <= 35 else title[:32] + "..."
        category = "论文研究"
        importance = "medium"
        
    elif source == "github_releases":
        summary = f"开源项目发布新版本，带来新功能和改进。{desc[:80]}" if desc else f"重要 AI 开源项目版本更新。"
        display_title = title if len(title) <= 35 else title[:32] + "..."
        category = "工具框架"
        importance = "medium"
        
    elif source == "36kr_ai":
        summary = desc[:120] if desc else f"36氪报道的 AI 行业最新动态。"
        display_title = title if len(title) <= 35 else title[:32] + "..."
        category = "行业动态"
        importance = "medium"
        
    elif source == "aibase":
        summary = desc[:120] if desc else f"AI Base 收录的新工具或资讯。"
        display_title = title if len(title) <= 35 else title[:32] + "..."
        category = "AI应用"
        importance = "low"
        
    elif source == "particle_news":
        summary = desc[:120] if desc else f"科技新闻聚合平台报道的 AI 相关动态。"
        display_title = title if len(title) <= 35 else title[:32] + "..."
        category = "行业动态"
        importance = "medium"
        
    elif source == "the_rundown_ai":
        summary = desc[:120] if desc else f"The Rundown AI Newsletter 精选的 AI 行业要闻。"
        display_title = title if len(title) <= 35 else title[:32] + "..."
        category = "行业动态"
        importance = "medium"
        
    elif source == "tldr_ai":
        summary = desc[:120] if desc else f"TLDR AI 简报精选内容。"
        display_title = title if len(title) <= 35 else title[:32] + "..."
        category = "行业动态"
        importance = "low"
        
    elif source == "product_hunt":
        summary = desc[:120] if desc else f"Product Hunt 上线的 AI 新产品，值得关注。"
        display_title = title if len(title) <= 35 else title[:32] + "..."
        category = "产品发布"
        importance = "medium"
        
    elif source == "toolify":
        summary = desc[:120] if desc else f"Toolify AI 工具排行榜上的热门工具。"
        display_title = title if len(title) <= 35 else title[:32] + "..."
        category = "AI应用"
        importance = "low"
        
    elif source == "chatpaper":
        summary = desc[:120] if desc else f"ChatPaper 推荐的 AI 前沿论文。"
        display_title = title if len(title) <= 35 else title[:32] + "..."
        category = "论文研究"
        importance = "medium"
    else:
        summary = desc[:120] if desc else title[:80]
        display_title = title if len(title) <= 35 else title[:32] + "..."
        category = "行业动态"
        importance = "low"
    
    return {
        "title": display_title,
        "summary": summary,
        "importance": importance,
        "category": category,
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

def generate_fallback_all(items):
    """完全降级方案（无 AI API）"""
    print("  [INFO] Using rule-based summary (no OPENAI_API_KEY)")
    results = []
    for item in items:
        results.append(generate_fallback_item(item))
    return results

def main():
    raw_data = load_raw_news()
    items = raw_data["items"]
    
    print("=" * 60)
    print("AI Summary Generation Start")
    print(f"   Items to process: {len(items)}")
    print("=" * 60)
    print()
    
    if os.environ.get("OPENAI_API_KEY"):
        print("  [KEY] OPENAI_API_KEY detected, using AI mode")
        news_items = generate_with_openai(items)
    else:
        print("  [WARN] No OPENAI_API_KEY, using rule-based mode")
        news_items = generate_fallback_all(items)
    
    # 排序：按重要性
    importance_order = {"high": 0, "medium": 1, "low": 2}
    news_items.sort(key=lambda x: importance_order.get(x.get("importance", "medium"), 1))
    
    # 计算统计
    beijing_tz = timezone(timedelta(hours=8))
    now_beijing = datetime.now(beijing_tz)
    
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date_display": now_beijing.strftime("%Y\u5e74%m\u6708%d\u65e5"),
        "date_short": now_beijing.strftime("%Y-%m-%d"),
        "total_items": len(news_items),
        "high_count": len([i for i in news_items if i.get("importance") == "high"]),
        "sources_count": len(set(i["source"] for i in news_items)),
        "items": news_items
    }
    
    with open("data/news_items.json", 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print()
    print("=" * 60)
    print(f"Summary complete! Total: {len(news_items)} items")
    print(f"   High: {output['high_count']} | Total: {output['total_items']}")
    print(f"   Saved to: data/news_items.json")
    print("=" * 60)

if __name__ == "__main__":
    main()
