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
        # 每组最多 20 条，避免 token 超限
        batch = group_items[:20]
        
        # 构造 prompt
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
        
        source_names = {
            "github_trending": "GitHub 热门项目",
            "hacker_news": "Hacker News 热帖",
            "ai_hot_feed": "AI 中文热点",
            "huggingface_papers": "AI 论文",
            "github_releases": "开源项目新版本",
        }
        
        prompt = f"""你是一个专业的 AI 行业资讯编辑。请基于以下来自"{source_names.get(source, source)}"的原始数据，为每条生成精炼的中文资讯条目。

原始数据：
{items_text}

请按以下 JSON 数组格式输出（仅输出 JSON，不要其他内容）：
[
  {{
    "title": "15-25字中文标题，简洁有力",
    "summary": "50-80字摘要，突出技术亮点和实际影响",
    "importance": "high/medium/low",
    "category": "模型发布/工具框架/开源项目/论文研究/行业动态/融资消息",
    "tags": ["标签1", "标签2"]
  }}
]

要求：
1. 标题必须是中文，有新闻感
2. 如果原标题已经是中文且足够好，保留
3. 过滤掉明显与 AI 无关的内容（返回空数组即可）
4. importance 判断：重大模型/产品发布=high，新功能/论文=medium，常规更新=low
5. 保持条目与原始数据顺序一致"""

        try:
            response = client.chat.completions.create(
                model=os.environ.get("AI_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=3000
            )
            result_text = response.choices[0].message.content.strip()
            
            # 清理 markdown 代码块
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1].rsplit("```", 1)[0]
            
            summaries = json.loads(result_text)
            
            # 合并原始数据和 AI 摘要
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
            
            print(f"  ✅ [{source_names.get(source, source)}] 生成 {len(summaries)} 条摘要")
            
        except Exception as e:
            print(f"  ⚠️ [{source}] AI 生成失败: {e}")
            # 降级：使用规则摘要
            for item in batch:
                news_items.append(generate_fallback_item(item))
    
    return news_items

def generate_fallback_item(item):
    """当 AI API 不可用时的降级摘要"""
    source = item["source"]
    title = item.get("title", "未知标题")
    desc = item.get("description", "")
    
    # 简单规则生成摘要
    if source == "github_trending":
        summary = f"GitHub 热门项目 {title}，{desc[:60]}" if desc else f"GitHub 热门 AI 项目：{title}"
        category = "开源项目"
    elif source == "hacker_news":
        summary = f"Hacker News 热议：{title}"
        category = "行业动态"
    elif source == "ai_hot_feed":
        summary = desc[:80] if desc else title
        category = "行业动态"
    elif source == "huggingface_papers":
        summary = f"最新 AI 论文：{title[:50]}"
        category = "论文研究"
    elif source == "github_releases":
        summary = f"开源项目更新：{title}"
        category = "工具框架"
    else:
        summary = desc[:80] if desc else title
        category = "行业动态"
    
    return {
        "title": title if len(title) <= 30 else title[:27] + "...",
        "summary": summary,
        "importance": "medium",
        "category": category,
        "tags": [source.replace("_", " ")],
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
    print("  ℹ️ 使用规则摘要模式（无 OPENAI_API_KEY）")
    results = []
    for item in items:
        results.append(generate_fallback_item(item))
    return results

def main():
    raw_data = load_raw_news()
    items = raw_data["items"]
    
    print("=" * 60)
    print("🤖 AI 摘要生成开始")
    print(f"   待处理: {len(items)} 条原始数据")
    print("=" * 60)
    print()
    
    # 判断是否有 API Key
    if os.environ.get("OPENAI_API_KEY"):
        print("  🔑 检测到 OPENAI_API_KEY，使用 AI 摘要模式")
        news_items = generate_with_openai(items)
    else:
        print("  ⚠️ 未设置 OPENAI_API_KEY，使用规则摘要模式")
        news_items = generate_fallback_all(items)
    
    # 排序：按重要性
    importance_order = {"high": 0, "medium": 1, "low": 2}
    news_items.sort(key=lambda x: importance_order.get(x.get("importance", "medium"), 1))
    
    # 计算统计
    beijing_tz = timezone(timedelta(hours=8))
    now_beijing = datetime.now(beijing_tz)
    
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date_display": now_beijing.strftime("%Y年%m月%d日"),
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
    print(f"✅ 摘要生成完成！共 {len(news_items)} 条资讯")
    print(f"   重要: {output['high_count']} | 总计: {output['total_items']}")
    print(f"   保存至: data/news_items.json")
    print("=" * 60)

if __name__ == "__main__":
    main()
