#!/usr/bin/env python3
"""
fetch_multi_source.py
从多个信源抓取 AI 相关资讯：
- GitHub Trending（AI/ML 热门项目）
- Hacker News（AI 相关热帖）
- AI HOT Feed（中文 AI 热点 RSS）
- Hugging Face Daily Papers（每日论文）
"""
import json
import os
import sys
import time
import requests
import feedparser
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# ========================= 配置 =========================
def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
}

# ========================= GitHub Trending =========================
def fetch_github_trending():
    """从 GitHub Trending 抓取 AI/ML 相关热门项目"""
    print("📡 [GitHub Trending] 开始抓取...")
    results = []
    
    # 抓取总趋势和 Python 语言趋势
    urls = [
        "https://github.com/trending?since=daily",
        "https://github.com/trending/python?since=daily",
    ]
    
    seen_repos = set()
    
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            articles = soup.select('article.Box-row')
            for article in articles[:30]:
                # 获取仓库名
                h2 = article.select_one('h2 a')
                if not h2:
                    continue
                repo_path = h2.get('href', '').strip('/')
                if not repo_path or repo_path in seen_repos:
                    continue
                
                # AI 关键词过滤
                desc_elem = article.select_one('p')
                desc = desc_elem.get_text(strip=True) if desc_elem else ""
                full_text = (repo_path + " " + desc).lower()
                
                ai_keywords = ['ai', 'llm', 'gpt', 'agent', 'ml', 'machine-learning',
                              'deep-learning', 'neural', 'transformer', 'diffusion',
                              'langchain', 'openai', 'anthropic', 'model', 'rag',
                              'embedding', 'nlp', 'vision', 'speech', 'inference',
                              'training', 'fine-tune', 'lora', 'quantiz']
                
                if not any(kw in full_text for kw in ai_keywords):
                    continue
                
                seen_repos.add(repo_path)
                
                # 获取 stars
                stars_elem = article.select_one('a[href*="/stargazers"]')
                stars = stars_elem.get_text(strip=True).replace(',', '') if stars_elem else "0"
                
                # 获取今日 star 增量
                today_stars_elem = article.select_one('span.d-inline-block.float-sm-right')
                today_stars = today_stars_elem.get_text(strip=True) if today_stars_elem else ""
                
                # 获取语言
                lang_elem = article.select_one('span[itemprop="programmingLanguage"]')
                language = lang_elem.get_text(strip=True) if lang_elem else ""
                
                results.append({
                    "source": "github_trending",
                    "title": repo_path,
                    "description": desc,
                    "url": f"https://github.com/{repo_path}",
                    "stars": stars,
                    "today_stars": today_stars,
                    "language": language,
                    "fetch_time": datetime.now(timezone.utc).isoformat()
                })
            
            time.sleep(1)  # 礼貌延迟
            
        except Exception as e:
            print(f"  ⚠️ 抓取 {url} 失败: {e}")
    
    print(f"  ✅ GitHub Trending: 获取 {len(results)} 个 AI 相关项目")
    return results

# ========================= Hacker News =========================
def fetch_hacker_news(config):
    """从 Hacker News API 获取 AI 相关热帖"""
    print("📡 [Hacker News] 开始抓取...")
    results = []
    
    hn_config = config["sources"]["hacker_news"]
    api_url = hn_config["api_url"]
    max_items = hn_config.get("max_items", 15)
    keywords = [kw.lower() for kw in hn_config.get("keywords", ["AI", "LLM", "GPT"])]
    
    try:
        # 获取 Top Stories
        resp = requests.get(f"{api_url}/topstories.json", timeout=15)
        resp.raise_for_status()
        story_ids = resp.json()[:100]  # 检查前 100 个
        
        ai_stories = []
        for story_id in story_ids:
            if len(ai_stories) >= max_items:
                break
            
            try:
                story_resp = requests.get(f"{api_url}/item/{story_id}.json", timeout=10)
                story = story_resp.json()
                
                if not story or story.get("type") != "story":
                    continue
                
                title = story.get("title", "")
                # AI 关键词匹配
                if any(kw in title.lower() for kw in keywords):
                    ai_stories.append({
                        "source": "hacker_news",
                        "title": title,
                        "description": "",
                        "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                        "hn_url": f"https://news.ycombinator.com/item?id={story_id}",
                        "score": story.get("score", 0),
                        "comments": story.get("descendants", 0),
                        "author": story.get("by", ""),
                        "fetch_time": datetime.now(timezone.utc).isoformat()
                    })
                
                time.sleep(0.1)  # API 礼貌延迟
                
            except Exception:
                continue
        
        results = ai_stories
        
    except Exception as e:
        print(f"  ⚠️ Hacker News API 失败: {e}")
    
    print(f"  ✅ Hacker News: 获取 {len(results)} 条 AI 相关帖子")
    return results

# ========================= AI HOT Feed =========================
def fetch_ai_hot_feed(config):
    """从 AI HOT Feed RSS 获取中文 AI 热点"""
    print("📡 [AI HOT Feed] 开始抓取...")
    results = []
    
    feed_url = config["sources"]["ai_hot_feed"]["feed_url"]
    max_items = config["sources"]["ai_hot_feed"].get("max_items", 20)
    
    try:
        feed = feedparser.parse(feed_url)
        
        for entry in feed.entries[:max_items]:
            results.append({
                "source": "ai_hot_feed",
                "title": entry.get("title", ""),
                "description": entry.get("summary", "")[:300],
                "url": entry.get("link", ""),
                "published": entry.get("published", ""),
                "fetch_time": datetime.now(timezone.utc).isoformat()
            })
        
    except Exception as e:
        print(f"  ⚠️ AI HOT Feed 失败: {e}")
    
    print(f"  ✅ AI HOT Feed: 获取 {len(results)} 条中文热点")
    return results

# ========================= Hugging Face Papers =========================
def fetch_huggingface_papers(config):
    """从 Hugging Face 获取每日 AI 论文"""
    print("📡 [Hugging Face Papers] 开始抓取...")
    results = []
    
    max_items = config["sources"]["huggingface_papers"].get("max_items", 10)
    
    try:
        resp = requests.get("https://huggingface.co/api/daily_papers", headers=HEADERS, timeout=15)
        resp.raise_for_status()
        papers = resp.json()
        
        for paper in papers[:max_items]:
            paper_info = paper.get("paper", {})
            results.append({
                "source": "huggingface_papers",
                "title": paper_info.get("title", ""),
                "description": paper_info.get("summary", "")[:400],
                "url": f"https://huggingface.co/papers/{paper_info.get('id', '')}",
                "arxiv_url": f"https://arxiv.org/abs/{paper_info.get('id', '')}",
                "upvotes": paper.get("paper", {}).get("upvotes", 0),
                "published": paper_info.get("publishedAt", ""),
                "fetch_time": datetime.now(timezone.utc).isoformat()
            })
        
    except Exception as e:
        print(f"  ⚠️ Hugging Face Papers 失败: {e}")
        # 降级方案：尝试 RSS
        try:
            feed = feedparser.parse("https://huggingface.co/papers/rss")
            for entry in feed.entries[:max_items]:
                results.append({
                    "source": "huggingface_papers",
                    "title": entry.get("title", ""),
                    "description": entry.get("summary", "")[:400],
                    "url": entry.get("link", ""),
                    "fetch_time": datetime.now(timezone.utc).isoformat()
                })
        except Exception as e2:
            print(f"  ⚠️ Hugging Face RSS 也失败了: {e2}")
    
    print(f"  ✅ Hugging Face Papers: 获取 {len(results)} 篇论文")
    return results

# ========================= GitHub Releases (补充) =========================
def fetch_github_ai_releases():
    """获取知名 AI 仓库的最新 releases"""
    print("📡 [GitHub Releases] 开始抓取...")
    results = []
    
    # 追踪的重要 AI 仓库
    important_repos = [
        "openai/openai-python",
        "langchain-ai/langchain",
        "huggingface/transformers",
        "vllm-project/vllm",
        "ollama/ollama",
        "meta-llama/llama",
        "microsoft/autogen",
        "Significant-Gravitas/AutoGPT",
        "crewAIInc/crewAI",
        "anthropics/anthropic-sdk-python",
    ]
    
    gh_token = os.environ.get("GH_TOKEN", "")
    headers = {**HEADERS, "Accept": "application/vnd.github.v3+json"}
    if gh_token:
        headers["Authorization"] = f"token {gh_token}"
    
    for repo in important_repos:
        try:
            resp = requests.get(
                f"https://api.github.com/repos/{repo}/releases",
                headers=headers, params={"per_page": 3}, timeout=10
            )
            if resp.status_code != 200:
                continue
            
            releases = resp.json()
            # 只获取最近 7 天内的 release
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            
            for release in releases:
                pub_date = release.get("published_at", "")
                if pub_date:
                    try:
                        pub_dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                        if pub_dt < cutoff:
                            continue
                    except:
                        pass
                
                results.append({
                    "source": "github_releases",
                    "title": f"{repo} 发布 {release.get('tag_name', '')}",
                    "description": (release.get("body", "") or "")[:300],
                    "url": release.get("html_url", ""),
                    "repo": repo,
                    "tag": release.get("tag_name", ""),
                    "published": pub_date,
                    "fetch_time": datetime.now(timezone.utc).isoformat()
                })
            
            time.sleep(0.5)
            
        except Exception as e:
            continue
    
    print(f"  ✅ GitHub Releases: 获取 {len(results)} 个新版本发布")
    return results

# ========================= 主流程 =========================
def main():
    config = load_config()
    
    print("=" * 60)
    print("🚀 AI 资讯多源抓取开始")
    print(f"   时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)
    print()
    
    all_items = []
    
    # 1. GitHub Trending
    if config["sources"]["github_trending"]["enabled"]:
        items = fetch_github_trending()
        all_items.extend(items)
    
    # 2. Hacker News
    if config["sources"]["hacker_news"]["enabled"]:
        items = fetch_hacker_news(config)
        all_items.extend(items)
    
    # 3. AI HOT Feed
    if config["sources"]["ai_hot_feed"]["enabled"]:
        items = fetch_ai_hot_feed(config)
        all_items.extend(items)
    
    # 4. Hugging Face Papers
    if config["sources"]["huggingface_papers"]["enabled"]:
        items = fetch_huggingface_papers(config)
        all_items.extend(items)
    
    # 5. GitHub Releases
    items = fetch_github_ai_releases()
    all_items.extend(items)
    
    # 保存原始数据
    os.makedirs("data", exist_ok=True)
    output = {
        "fetch_time": datetime.now(timezone.utc).isoformat(),
        "total_items": len(all_items),
        "sources_summary": {
            "github_trending": len([i for i in all_items if i["source"] == "github_trending"]),
            "hacker_news": len([i for i in all_items if i["source"] == "hacker_news"]),
            "ai_hot_feed": len([i for i in all_items if i["source"] == "ai_hot_feed"]),
            "huggingface_papers": len([i for i in all_items if i["source"] == "huggingface_papers"]),
            "github_releases": len([i for i in all_items if i["source"] == "github_releases"]),
        },
        "items": all_items
    }
    
    with open("data/raw_news.json", 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print()
    print("=" * 60)
    print(f"✅ 抓取完成！共获取 {len(all_items)} 条资讯")
    for source, count in output["sources_summary"].items():
        print(f"   • {source}: {count} 条")
    print(f"   保存至: data/raw_news.json")
    print("=" * 60)

if __name__ == "__main__":
    main()
