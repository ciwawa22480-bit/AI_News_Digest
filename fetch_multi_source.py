#!/usr/bin/env python3
"""
fetch_multi_source.py
从多个信源抓取 AI 相关资讯：
- GitHub Trending（AI/ML 热门项目）
- Hacker News（AI 相关热帖）
- AI HOT Feed（中文 AI 热点 RSS）
- Hugging Face Daily Papers（每日论文）
- 36Kr AI 专栏
- AI Base 综合资讯
- Particle News 科技聚合
- The Rundown AI Newsletter
- TLDR AI Newsletter
- Product Hunt AI 新产品
- Toolify AI 工具榜
- ChatPaper AI 论文
"""
import json
import os
import sys
import time
import re
import requests
import feedparser
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# ========================= 配置 =========================
def load_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
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
    print("[GitHub Trending] start...")
    results = []
    
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
                h2 = article.select_one('h2 a')
                if not h2:
                    continue
                repo_path = h2.get('href', '').strip('/')
                if not repo_path or repo_path in seen_repos:
                    continue
                
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
                
                stars_elem = article.select_one('a[href*="/stargazers"]')
                stars = stars_elem.get_text(strip=True).replace(',', '') if stars_elem else "0"
                
                today_stars_elem = article.select_one('span.d-inline-block.float-sm-right')
                today_stars = today_stars_elem.get_text(strip=True) if today_stars_elem else ""
                
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
            
            time.sleep(1)
            
        except Exception as e:
            print(f"  [WARN] fetch {url} failed: {e}")
    
    print(f"  [OK] GitHub Trending: {len(results)} AI projects")
    return results

# ========================= Hacker News =========================
def fetch_hacker_news(config):
    """从 Hacker News API 获取 AI 相关热帖"""
    print("[Hacker News] start...")
    results = []
    
    hn_config = config["sources"]["hacker_news"]
    api_url = hn_config["api_url"]
    max_items = hn_config.get("max_items", 15)
    keywords = [kw.lower() for kw in hn_config.get("keywords", ["AI", "LLM", "GPT"])]
    
    try:
        resp = requests.get(f"{api_url}/topstories.json", timeout=15)
        resp.raise_for_status()
        story_ids = resp.json()[:100]
        
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
                
                time.sleep(0.1)
                
            except Exception:
                continue
        
        results = ai_stories
        
    except Exception as e:
        print(f"  [WARN] Hacker News API failed: {e}")
    
    print(f"  [OK] Hacker News: {len(results)} AI posts")
    return results

# ========================= AI HOT Feed =========================
def fetch_ai_hot_feed(config):
    """从 AI HOT Feed RSS 获取中文 AI 热点"""
    print("[AI HOT Feed] start...")
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
        print(f"  [WARN] AI HOT Feed failed: {e}")
    
    print(f"  [OK] AI HOT Feed: {len(results)} items")
    return results

# ========================= Hugging Face Papers =========================
def fetch_huggingface_papers(config):
    """从 Hugging Face 获取每日 AI 论文"""
    print("[Hugging Face Papers] start...")
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
        print(f"  [WARN] Hugging Face Papers failed: {e}")
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
            print(f"  [WARN] Hugging Face RSS also failed: {e2}")
    
    print(f"  [OK] Hugging Face Papers: {len(results)} papers")
    return results

# ========================= GitHub Releases =========================
def fetch_github_ai_releases():
    """获取知名 AI 仓库的最新 releases"""
    print("[GitHub Releases] start...")
    results = []
    
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
                    "title": f"{repo} released {release.get('tag_name', '')}",
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
    
    print(f"  [OK] GitHub Releases: {len(results)} new releases")
    return results

# ========================= 36Kr AI =========================
def fetch_36kr_ai(config):
    """从 36Kr AI 专栏抓取最新资讯"""
    print("[36Kr AI] start...")
    results = []
    
    src_config = config["sources"].get("kr36_ai", {})
    if not src_config.get("enabled", False):
        return results
    
    max_items = src_config.get("max_items", 15)
    url = src_config.get("url", "https://36kr.com/information/AI/")
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 36Kr 文章列表
        articles = soup.select('a.article-item-title, a[class*="title"], div.article-item a')
        seen_urls = set()
        
        for article in articles[:max_items * 2]:
            title = article.get_text(strip=True)
            href = article.get('href', '')
            
            if not title or len(title) < 5:
                continue
            
            if href and not href.startswith('http'):
                href = f"https://36kr.com{href}"
            
            if href in seen_urls:
                continue
            seen_urls.add(href)
            
            results.append({
                "source": "36kr_ai",
                "title": title,
                "description": "",
                "url": href,
                "fetch_time": datetime.now(timezone.utc).isoformat()
            })
            
            if len(results) >= max_items:
                break
        
        # 如果网页抓取结果少，尝试 RSS
        if len(results) < 3:
            rss_url = src_config.get("rss_url", "")
            if rss_url:
                feed = feedparser.parse(rss_url)
                for entry in feed.entries[:max_items]:
                    if entry.get("link") not in seen_urls:
                        results.append({
                            "source": "36kr_ai",
                            "title": entry.get("title", ""),
                            "description": entry.get("summary", "")[:200],
                            "url": entry.get("link", ""),
                            "published": entry.get("published", ""),
                            "fetch_time": datetime.now(timezone.utc).isoformat()
                        })
    
    except Exception as e:
        print(f"  [WARN] 36Kr AI failed: {e}")
    
    print(f"  [OK] 36Kr AI: {len(results)} articles")
    return results

# ========================= AI Base =========================
def fetch_aibase(config):
    """从 AI Base 抓取 AI 工具和资讯"""
    print("[AI Base] start...")
    results = []
    
    src_config = config["sources"].get("aibase", {})
    if not src_config.get("enabled", False):
        return results
    
    max_items = src_config.get("max_items", 15)
    url = src_config.get("url", "https://www.aibase.com/zh")
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 尝试多种选择器匹配 AI Base 的文章列表
        articles = soup.select('a[href*="/tool/"], a[href*="/news/"], div.card a, article a')
        seen_urls = set()
        
        for article in articles:
            title = article.get_text(strip=True)
            href = article.get('href', '')
            
            if not title or len(title) < 4:
                continue
            
            if href and not href.startswith('http'):
                href = f"https://www.aibase.com{href}"
            
            if href in seen_urls:
                continue
            seen_urls.add(href)
            
            results.append({
                "source": "aibase",
                "title": title,
                "description": "",
                "url": href,
                "fetch_time": datetime.now(timezone.utc).isoformat()
            })
            
            if len(results) >= max_items:
                break
    
    except Exception as e:
        print(f"  [WARN] AI Base failed: {e}")
    
    print(f"  [OK] AI Base: {len(results)} items")
    return results

# ========================= Particle News =========================
def fetch_particle_news(config):
    """从 Particle News 抓取 AI/科技聚合资讯"""
    print("[Particle News] start...")
    results = []
    
    src_config = config["sources"].get("particle_news", {})
    if not src_config.get("enabled", False):
        return results
    
    max_items = src_config.get("max_items", 15)
    url = src_config.get("url", "https://particle.news/technology")
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Particle News 文章卡片
        articles = soup.select('a[href*="/s/"], article a, div[class*="card"] a, h2 a, h3 a')
        seen_urls = set()
        
        for article in articles:
            title = article.get_text(strip=True)
            href = article.get('href', '')
            
            if not title or len(title) < 5:
                continue
            
            if href and not href.startswith('http'):
                href = f"https://particle.news{href}"
            
            if href in seen_urls:
                continue
            seen_urls.add(href)
            
            # AI 关键词过滤
            title_lower = title.lower()
            ai_keywords = ['ai', 'gpt', 'llm', 'openai', 'anthropic', 'google', 'meta',
                          'machine learning', 'neural', 'robot', 'automation', 'chatbot',
                          'model', 'nvidia', 'chip', 'compute']
            
            if any(kw in title_lower for kw in ai_keywords):
                results.append({
                    "source": "particle_news",
                    "title": title,
                    "description": "",
                    "url": href,
                    "fetch_time": datetime.now(timezone.utc).isoformat()
                })
            
            if len(results) >= max_items:
                break
    
    except Exception as e:
        print(f"  [WARN] Particle News failed: {e}")
    
    print(f"  [OK] Particle News: {len(results)} items")
    return results

# ========================= The Rundown AI =========================
def fetch_the_rundown_ai(config):
    """从 The Rundown AI 抓取 Newsletter 内容"""
    print("[The Rundown AI] start...")
    results = []
    
    src_config = config["sources"].get("the_rundown_ai", {})
    if not src_config.get("enabled", False):
        return results
    
    max_items = src_config.get("max_items", 10)
    url = src_config.get("url", "https://www.therundown.ai/")
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # The Rundown AI 文章/帖子
        articles = soup.select('a[href*="/p/"], article a, h2 a, h3 a, div[class*="post"] a')
        seen_urls = set()
        
        for article in articles:
            title = article.get_text(strip=True)
            href = article.get('href', '')
            
            if not title or len(title) < 8:
                continue
            
            if href and not href.startswith('http'):
                href = f"https://www.therundown.ai{href}"
            
            if href in seen_urls:
                continue
            seen_urls.add(href)
            
            results.append({
                "source": "the_rundown_ai",
                "title": title,
                "description": "",
                "url": href,
                "fetch_time": datetime.now(timezone.utc).isoformat()
            })
            
            if len(results) >= max_items:
                break
    
    except Exception as e:
        print(f"  [WARN] The Rundown AI failed: {e}")
    
    print(f"  [OK] The Rundown AI: {len(results)} items")
    return results

# ========================= TLDR AI =========================
def fetch_tldr(config):
    """从 TLDR AI Newsletter 抓取内容"""
    print("[TLDR AI] start...")
    results = []
    
    src_config = config["sources"].get("tldr", {})
    if not src_config.get("enabled", False):
        return results
    
    max_items = src_config.get("max_items", 10)
    url = src_config.get("url", "https://tldr.tech/ai")
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # TLDR 文章链接
        articles = soup.select('a[href*="/ai/"], article a, h3 a, div[class*="article"] a, div[class*="newsletter"] a')
        seen_urls = set()
        
        for article in articles:
            title = article.get_text(strip=True)
            href = article.get('href', '')
            
            if not title or len(title) < 8:
                continue
            
            if href and not href.startswith('http'):
                href = f"https://tldr.tech{href}"
            
            if href in seen_urls:
                continue
            seen_urls.add(href)
            
            results.append({
                "source": "tldr_ai",
                "title": title,
                "description": "",
                "url": href,
                "fetch_time": datetime.now(timezone.utc).isoformat()
            })
            
            if len(results) >= max_items:
                break
    
    except Exception as e:
        print(f"  [WARN] TLDR AI failed: {e}")
    
    print(f"  [OK] TLDR AI: {len(results)} items")
    return results

# ========================= Product Hunt =========================
def fetch_product_hunt(config):
    """从 Product Hunt 抓取 AI 相关新产品"""
    print("[Product Hunt] start...")
    results = []
    
    src_config = config["sources"].get("product_hunt", {})
    if not src_config.get("enabled", False):
        return results
    
    max_items = src_config.get("max_items", 15)
    keywords = [kw.lower() for kw in src_config.get("keywords", ["AI", "GPT", "LLM"])]
    url = src_config.get("url", "https://www.producthunt.com/")
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Product Hunt 产品卡片
        products = soup.select('a[href*="/posts/"], div[class*="product"] a, h3 a')
        seen_urls = set()
        
        for product in products:
            title = product.get_text(strip=True)
            href = product.get('href', '')
            
            if not title or len(title) < 3:
                continue
            
            if href and not href.startswith('http'):
                href = f"https://www.producthunt.com{href}"
            
            if href in seen_urls:
                continue
            seen_urls.add(href)
            
            # 获取描述（可能在相邻元素）
            desc = ""
            parent = product.parent
            if parent:
                desc_elem = parent.select_one('p, span[class*="tagline"], span[class*="desc"]')
                if desc_elem:
                    desc = desc_elem.get_text(strip=True)
            
            # AI 关键词过滤
            full_text = (title + " " + desc).lower()
            if any(kw in full_text for kw in keywords):
                results.append({
                    "source": "product_hunt",
                    "title": title,
                    "description": desc[:200],
                    "url": href,
                    "fetch_time": datetime.now(timezone.utc).isoformat()
                })
            
            if len(results) >= max_items:
                break
    
    except Exception as e:
        print(f"  [WARN] Product Hunt failed: {e}")
    
    print(f"  [OK] Product Hunt: {len(results)} AI products")
    return results

# ========================= Toolify =========================
def fetch_toolify(config):
    """从 Toolify 抓取热门 AI 工具榜"""
    print("[Toolify] start...")
    results = []
    
    src_config = config["sources"].get("toolify", {})
    if not src_config.get("enabled", False):
        return results
    
    max_items = src_config.get("max_items", 15)
    url = src_config.get("url", "https://www.toolify.ai/Best-trending-AI-Tools")
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Toolify 工具卡片
        tools = soup.select('a[href*="/tool/"], div[class*="tool"] a, h3 a, div[class*="card"] a')
        seen_urls = set()
        
        for tool in tools:
            title = tool.get_text(strip=True)
            href = tool.get('href', '')
            
            if not title or len(title) < 2:
                continue
            
            if href and not href.startswith('http'):
                href = f"https://www.toolify.ai{href}"
            
            if href in seen_urls:
                continue
            seen_urls.add(href)
            
            # 获取描述
            desc = ""
            parent = tool.parent
            if parent:
                desc_elem = parent.select_one('p, span[class*="desc"]')
                if desc_elem:
                    desc = desc_elem.get_text(strip=True)
            
            results.append({
                "source": "toolify",
                "title": title,
                "description": desc[:200],
                "url": href,
                "fetch_time": datetime.now(timezone.utc).isoformat()
            })
            
            if len(results) >= max_items:
                break
    
    except Exception as e:
        print(f"  [WARN] Toolify failed: {e}")
    
    print(f"  [OK] Toolify: {len(results)} AI tools")
    return results

# ========================= ChatPaper =========================
def fetch_chatpaper(config):
    """从 ChatPaper 抓取 AI 论文推荐"""
    print("[ChatPaper] start...")
    results = []
    
    src_config = config["sources"].get("chatpaper", {})
    if not src_config.get("enabled", False):
        return results
    
    max_items = src_config.get("max_items", 10)
    
    # 使用当天日期
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://www.chatpaper.ai/zh/dashboard/papers/{today}"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # ChatPaper 论文列表
        papers = soup.select('a[href*="/paper/"], div[class*="paper"] a, h3 a, article a')
        seen_urls = set()
        
        for paper in papers:
            title = paper.get_text(strip=True)
            href = paper.get('href', '')
            
            if not title or len(title) < 10:
                continue
            
            if href and not href.startswith('http'):
                href = f"https://www.chatpaper.ai{href}"
            
            if href in seen_urls:
                continue
            seen_urls.add(href)
            
            results.append({
                "source": "chatpaper",
                "title": title,
                "description": "",
                "url": href,
                "fetch_time": datetime.now(timezone.utc).isoformat()
            })
            
            if len(results) >= max_items:
                break
    
    except Exception as e:
        print(f"  [WARN] ChatPaper failed: {e}")
    
    print(f"  [OK] ChatPaper: {len(results)} papers")
    return results

# ========================= 主流程 =========================
def main():
    config = load_config()
    
    print("=" * 60)
    print("AI News Multi-Source Fetch Start")
    print(f"   Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)
    print()
    
    all_items = []
    
    # 1. GitHub Trending
    if config["sources"].get("github_trending", {}).get("enabled"):
        items = fetch_github_trending()
        all_items.extend(items)
    
    # 2. Hacker News
    if config["sources"].get("hacker_news", {}).get("enabled"):
        items = fetch_hacker_news(config)
        all_items.extend(items)
    
    # 3. AI HOT Feed
    if config["sources"].get("ai_hot_feed", {}).get("enabled"):
        items = fetch_ai_hot_feed(config)
        all_items.extend(items)
    
    # 4. Hugging Face Papers
    if config["sources"].get("huggingface_papers", {}).get("enabled"):
        items = fetch_huggingface_papers(config)
        all_items.extend(items)
    
    # 5. GitHub Releases
    items = fetch_github_ai_releases()
    all_items.extend(items)
    
    # 6. 36Kr AI
    if config["sources"].get("kr36_ai", {}).get("enabled"):
        items = fetch_36kr_ai(config)
        all_items.extend(items)
    
    # 7. AI Base
    if config["sources"].get("aibase", {}).get("enabled"):
        items = fetch_aibase(config)
        all_items.extend(items)
    
    # 8. Particle News
    if config["sources"].get("particle_news", {}).get("enabled"):
        items = fetch_particle_news(config)
        all_items.extend(items)
    
    # 9. The Rundown AI
    if config["sources"].get("the_rundown_ai", {}).get("enabled"):
        items = fetch_the_rundown_ai(config)
        all_items.extend(items)
    
    # 10. TLDR AI
    if config["sources"].get("tldr", {}).get("enabled"):
        items = fetch_tldr(config)
        all_items.extend(items)
    
    # 11. Product Hunt
    if config["sources"].get("product_hunt", {}).get("enabled"):
        items = fetch_product_hunt(config)
        all_items.extend(items)
    
    # 12. Toolify
    if config["sources"].get("toolify", {}).get("enabled"):
        items = fetch_toolify(config)
        all_items.extend(items)
    
    # 13. ChatPaper
    if config["sources"].get("chatpaper", {}).get("enabled"):
        items = fetch_chatpaper(config)
        all_items.extend(items)
    
    # 保存原始数据
    os.makedirs("data", exist_ok=True)
    
    # 统计各来源数量
    source_names = [
        "github_trending", "hacker_news", "ai_hot_feed", "huggingface_papers",
        "github_releases", "36kr_ai", "aibase", "particle_news",
        "the_rundown_ai", "tldr_ai", "product_hunt", "toolify", "chatpaper"
    ]
    sources_summary = {}
    for name in source_names:
        count = len([i for i in all_items if i["source"] == name])
        if count > 0:
            sources_summary[name] = count
    
    output = {
        "fetch_time": datetime.now(timezone.utc).isoformat(),
        "total_items": len(all_items),
        "sources_summary": sources_summary,
        "items": all_items
    }
    
    with open("data/raw_news.json", 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print()
    print("=" * 60)
    print(f"Fetch complete! Total: {len(all_items)} items")
    for source, count in sources_summary.items():
        print(f"   - {source}: {count}")
    print(f"   Saved to: data/raw_news.json")
    print("=" * 60)

if __name__ == "__main__":
    main()
