#!/usr/bin/env python3
"""
URL 粒度校验器（gate0.5）
用法:
    python3 validate_urls.py <data_file_or_dir> [--strict] [--fix-empty]

功能:
    遍历采集产物 (JSON / JSONL)，对每条 item.url 字段做"是否原文页"判定。
    检测出"首页/根域名"型兜底 URL，打印审计报告。

判定规则（白名单 + 启发式）:
    1. 必须 http/https
    2. 路径不能是 /、/index.html、/news、/blog、/articles 等纯导航页
    3. 路径深度 >= 1 段，且最后一段 slug 长度 >= 6（粗略文章 slug 检测）
       例外: 已知短链/聚合站规则 (news.ycombinator.com/item, github.com/owner/repo,
            arxiv.org/abs/xxxx)
    4. 域名 == 路径根 视为首页

退出码:
    0  全部通过 / 无问题
    1  存在首页型 URL（>10% 阈值即 FAIL）
    2  脚本错误

设计原则:
    - 零依赖 (只用标准库)
    - 可被 SKILL.md gate0.5 / pipeline 调用
    - 输出 JSON 报告到 stdout, 人类可读摘要到 stderr
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# ---- 已知"原文 URL pattern"白名单 (path 命中即视为合法原文链) ----
ARTICLE_PATTERNS = [
    re.compile(r"^/item\?id=\d+"),                       # HN
    re.compile(r"^/[\w.-]+/[\w.-]+/?$"),                 # github.com/owner/repo
    re.compile(r"^/abs/\d+\.\d+"),                       # arxiv.org/abs/xxxx
    re.compile(r"^/papers/\d+\.\d+"),                    # huggingface papers
    re.compile(r"^/p/[\w-]+"),                           # substack post
    re.compile(r"^/\d{4}/\d{1,2}/\d{1,2}/"),             # 日期式新闻 URL
    re.compile(r"/(article|articles|news|posts|blog)/[\w-]{6,}"),  # /article/xxxxx
    re.compile(r"/post/\d+"),                            # 微博/qq/36kr 类
    re.compile(r"/[\w-]{8,}\.(html|htm|shtml)$"),        # *.html 文章页
    re.compile(r"/status/\d+"),                          # x.com/twitter
    re.compile(r"/posts/[\w-]+"),
]

# ---- 纯导航 / 首页 path 黑名单 ----
NAV_PATHS = {
    "", "/", "/index.html", "/index", "/home",
    "/news", "/news/", "/blog", "/blog/", "/articles", "/articles/",
    "/papers", "/papers/", "/posts", "/posts/", "/feed", "/rss",
    "/about", "/contact", "/category", "/tags", "/topics",
}


def is_article_url(url: str) -> tuple[bool, str]:
    """
    返回 (是否合法原文 URL, 原因说明)
    """
    if not url or not isinstance(url, str):
        return False, "空 URL"
    if not url.startswith(("http://", "https://")):
        return False, f"非 http(s) 协议: {url[:40]}"
    try:
        p = urlparse(url)
    except Exception as exc:
        return False, f"URL 解析失败: {exc}"

    path = p.path or "/"
    # path + query 一起做 pattern 匹配（HN ?id=xxx 之类需要看 query）
    path_q = path + (("?" + p.query) if p.query else "")

    # 1) 黑名单：纯导航
    if path in NAV_PATHS:
        return False, f"导航/首页 path: {path!r}"

    # 2) 白名单：明确的文章 URL pattern
    for pat in ARTICLE_PATTERNS:
        if pat.search(path_q):
            return True, "命中文章 pattern"

    # 2.5) query 里带 id=数字 的也视为文章页 (HN/Reddit/旧式 CMS)
    if re.search(r"\b(id|p|story|article)=\d+", p.query):
        return True, "query 含数字 ID"

    # 3) 启发式：path 深度 + 末段 slug 长度
    segs = [s for s in path.split("/") if s]
    if len(segs) == 0:
        return False, "path 为空"
    last = segs[-1]
    # 末段如果是纯数字 ID（>=4 位）也视为文章
    if last.isdigit() and len(last) >= 4:
        return True, "末段为数字 ID"
    # 末段 slug 至少 6 字符 + 含字母
    if len(last) >= 6 and re.search(r"[a-zA-Z一-龥]", last):
        return True, "末段 slug 长度 >=6"

    # 4) 默认拒绝
    return False, f"path 过浅或无 slug: {path!r}"


def load_items(path: Path) -> list[dict[str, Any]]:
    """支持 JSON 数组 / 单对象 / JSONL"""
    text = path.read_text(encoding="utf-8")
    text_strip = text.strip()
    # JSONL
    if "\n" in text_strip and text_strip.startswith("{"):
        try:
            return [json.loads(line) for line in text_strip.splitlines() if line.strip()]
        except json.JSONDecodeError:
            pass
    data = json.loads(text)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # 常见 wrapper key
        for k in ("items", "news", "data", "results", "articles", "list"):
            if k in data and isinstance(data[k], list):
                return data[k]
        return [data]
    return []


def audit_file(path: Path) -> dict[str, Any]:
    items = load_items(path)
    bad: list[dict[str, Any]] = []
    good = 0
    no_url = 0
    for idx, it in enumerate(items):
        if not isinstance(it, dict):
            continue
        url = it.get("url") or it.get("link") or it.get("href") or ""
        if not url:
            no_url += 1
            continue
        ok, reason = is_article_url(url)
        if ok:
            good += 1
        else:
            bad.append({
                "idx": idx,
                "title": (it.get("title") or "")[:80],
                "source": it.get("source", ""),
                "url": url,
                "reason": reason,
            })
    total = good + len(bad) + no_url
    bad_ratio = len(bad) / total if total else 0
    return {
        "file": str(path),
        "total": total,
        "good": good,
        "bad": len(bad),
        "no_url": no_url,
        "bad_ratio": round(bad_ratio, 3),
        "bad_items": bad,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="URL 粒度校验器 (gate0.5)")
    ap.add_argument("target", help="要审计的 JSON 文件或目录")
    ap.add_argument("--threshold", type=float, default=0.10,
                    help="bad_ratio 阈值, 超过即 FAIL (默认 0.10)")
    ap.add_argument("--quiet", action="store_true", help="只打印汇总")
    ap.add_argument("--json-out", type=str, default=None,
                    help="审计报告写入文件, 而非 stdout")
    args = ap.parse_args()

    target = Path(args.target)
    if not target.exists():
        print(f"❌ 路径不存在: {target}", file=sys.stderr)
        return 2

    files: list[Path] = []
    if target.is_dir():
        files = sorted([p for p in target.glob("*.json") if p.is_file()])
    else:
        files = [target]

    reports: list[dict[str, Any]] = []
    overall_total = 0
    overall_bad = 0
    for f in files:
        try:
            r = audit_file(f)
        except Exception as exc:
            print(f"⚠️  {f} 读取失败: {exc}", file=sys.stderr)
            continue
        reports.append(r)
        overall_total += r["total"]
        overall_bad += r["bad"]

    overall_ratio = overall_bad / overall_total if overall_total else 0
    summary = {
        "files_audited": len(reports),
        "overall_total_items": overall_total,
        "overall_bad_items": overall_bad,
        "overall_bad_ratio": round(overall_ratio, 3),
        "threshold": args.threshold,
        "verdict": "FAIL" if overall_ratio > args.threshold else "PASS",
        "per_file": reports,
    }

    out_text = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(out_text, encoding="utf-8")
    else:
        print(out_text)

    # 人类可读摘要 → stderr
    print("\n" + "=" * 60, file=sys.stderr)
    print(f"📊 URL 粒度校验报告", file=sys.stderr)
    print(f"   审计文件数:   {len(reports)}", file=sys.stderr)
    print(f"   总条目数:     {overall_total}", file=sys.stderr)
    print(f"   首页型 URL:   {overall_bad} ({overall_ratio:.1%})", file=sys.stderr)
    print(f"   阈值:         {args.threshold:.0%}", file=sys.stderr)
    print(f"   判定:         {summary['verdict']}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    if not args.quiet:
        for r in reports:
            if r["bad"] == 0:
                continue
            print(f"\n📄 {r['file']}  bad={r['bad']}/{r['total']} ({r['bad_ratio']:.1%})",
                  file=sys.stderr)
            for b in r["bad_items"][:10]:
                print(f"   [{b['idx']:>2}] {b['source']:<14} {b['url']}", file=sys.stderr)
                print(f"        ↳ {b['title']}", file=sys.stderr)
                print(f"        ↳ 原因: {b['reason']}", file=sys.stderr)

    return 1 if summary["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
