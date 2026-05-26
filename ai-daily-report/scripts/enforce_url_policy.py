#!/usr/bin/env python3
"""
URL 兜底规整器 (gate0.6)
用法:
    python3 enforce_url_policy.py <data_file> [--in-place] [--report report.json]

逻辑:
    对采集产物里所有"首页型 URL"item:
      - 把 url 字段置为空字符串 ""
      - 在 source 后追加 "（综合报道）" 标记
      - item['url_demoted'] = True (供下游审计)
    对合法原文 URL 不做任何改动。

设计原则:
    - 与 SKILL.md 第 400 行硬约束对齐:
      "实在找不到一手 URL 时, 标注'综合报道'并在 URL 列留空"
    - 必须在 fetch_news.py / news-aggregator 输出后, 进入 merge/render 之前调用
    - 默认 dry-run 输出到 stdout, 加 --in-place 才回写
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 复用同目录的 validate_urls
sys.path.insert(0, str(Path(__file__).parent))
from validate_urls import is_article_url, load_items  # noqa: E402


def enforce_one(item: dict) -> tuple[dict, bool]:
    """返回 (修改后的 item, 是否被降级)"""
    url = item.get("url") or item.get("link") or ""
    if not url:
        return item, False
    ok, _ = is_article_url(url)
    if ok:
        return item, False
    # 降级
    new = dict(item)
    new["url"] = ""
    new["url_demoted"] = True
    new["original_url"] = url  # 保留原值供审计
    src = new.get("source", "") or ""
    if "综合报道" not in src:
        new["source"] = (src + "（综合报道）").lstrip("（")
    return new, True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="data 文件 (单个 JSON)")
    ap.add_argument("--in-place", action="store_true", help="回写原文件")
    ap.add_argument("--report", type=str, default=None, help="审计报告输出路径")
    args = ap.parse_args()

    target = Path(args.target)
    items = load_items(target)
    new_items = []
    demoted = []
    for it in items:
        if not isinstance(it, dict):
            new_items.append(it)
            continue
        ni, was = enforce_one(it)
        new_items.append(ni)
        if was:
            demoted.append({
                "title": (ni.get("title") or "")[:80],
                "original_url": ni.get("original_url", ""),
                "source": ni.get("source", ""),
            })

    out = json.dumps(new_items, ensure_ascii=False, indent=2)
    if args.in_place:
        target.write_text(out, encoding="utf-8")
        print(f"✅ 回写完成: {target}", file=sys.stderr)
    else:
        print(out)

    print(f"\n📊 降级统计: {len(demoted)} / {len(items)} 条 URL 被置空",
          file=sys.stderr)
    for d in demoted[:10]:
        print(f"   - {d['source']:<20} {d['original_url']}", file=sys.stderr)
        print(f"     {d['title']}", file=sys.stderr)

    if args.report:
        Path(args.report).write_text(
            json.dumps({"demoted_count": len(demoted),
                        "demoted_items": demoted}, ensure_ascii=False, indent=2),
            encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
