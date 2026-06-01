"""gate_g08_version_consistency: Kleisli node that flags items mentioning
product versions inconsistent with the latest known version in ctx.version_registry.

Example: when ctx.version_registry["claude opus"]="4.8", any item title or summary
mentioning "Claude Opus 4.5" alongside the 4.8 release news is flagged as WARN
(not FAIL — old-version mentions can be legitimate context).

The gate emits a structured trace consumed by stage9_kleisli to render a banner.
"""
from __future__ import annotations
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.effect import Ctx, Report, kleisli  # noqa: E402

DATA_DIR = Path("/data/userdata/daily-report/data")
REPORT_DATE = date(2026, 6, 1)


# Version patterns. Each product key (lowercase) -> compiled regex extractor
# that yields normalized version strings (e.g., "4.5", "4.8").
VERSION_PATTERNS: dict[str, re.Pattern] = {
    "claude opus": re.compile(r"opus\s*v?(\d+\.\d+)", re.IGNORECASE),
    "claude sonnet": re.compile(r"sonnet\s*v?(\d+\.\d+)", re.IGNORECASE),
    "gpt": re.compile(r"gpt[\s\-]?(\d+\.?\d*)", re.IGNORECASE),
    "gemini": re.compile(r"gemini\s*v?(\d+\.\d+)", re.IGNORECASE),
}


def gate_g08_version_consistency(items: list[dict], ctx: Ctx) -> Report[list[dict]]:
    conflicts = []
    for product_key, latest in ctx.version_registry.items():
        pattern = VERSION_PATTERNS.get(product_key)
        if not pattern:
            continue
        latest_versions: set[str] = set()
        stale_versions: set[str] = set()
        latest_titles: list[str] = []
        stale_titles: list[str] = []
        for it in items:
            text = (it.get("title", "") + " " + (it.get("summary", "") or "") + " "
                    + " ".join(it.get("consensus", []) if isinstance(it.get("consensus"), list) else []))
            for m in pattern.findall(text):
                ver = m.strip()
                if ver == latest:
                    latest_versions.add(ver)
                    latest_titles.append(it["title"][:50])
                else:
                    stale_versions.add(ver)
                    stale_titles.append(f"{ver}: {it['title'][:40]}")
        if latest_versions and stale_versions:
            conflicts.append({
                "product": product_key,
                "latest": latest,
                "stale_versions": sorted(stale_versions),
                "latest_mentions": latest_titles[:5],
                "stale_mentions": stale_titles[:5],
            })

    if not conflicts:
        return Report(items, "OK",
                      [f"G0.8 version-consistency: {len(VERSION_PATTERNS)} products checked, no conflicts ✓"],
                      ctx)

    evid = [f"G0.8 version-consistency: {len(conflicts)} conflict(s)"]
    for c in conflicts:
        evid.append(f"  · {c['product']} latest={c['latest']} but stale_versions={c['stale_versions']}")
        for st in c["stale_mentions"][:3]:
            evid.append(f"      stale: {st}")
    evid.append("  → status=WARN (banner injected; items kept)")
    return Report(items, "WARN", evid, ctx)


def main() -> int:
    in_path = DATA_DIR / "07b-deduped.json"
    if not in_path.exists():
        in_path = DATA_DIR / "07-merged.json"
    items = json.loads(in_path.read_text(encoding="utf-8"))

    ctx = Ctx(
        report_date=REPORT_DATE,
        recent_window=tuple(REPORT_DATE - timedelta(days=i) for i in range(4)),
        archive_index={},
        version_registry={
            "claude opus": "4.8",
            "claude sonnet": "4.8",
            "gpt": "5.2",
            "gemini": "3.0",
        },
        data_dir=str(DATA_DIR),
    )

    seed = Report(items, "OK", [f"input: {in_path.name} n={len(items)}"], ctx)
    pipeline = kleisli(gate_g08_version_consistency)
    result = pipeline(seed)

    out_path = DATA_DIR / "07c-version-trace.json"
    # Re-run pattern matching to harvest the structured conflict payload
    conflicts_payload = []
    for product_key, latest in ctx.version_registry.items():
        pattern = VERSION_PATTERNS.get(product_key)
        if not pattern:
            continue
        latest_versions, stale_versions, stale_titles = set(), set(), []
        for it in items:
            text = it.get("title", "") + " " + (it.get("summary", "") or "")
            for m in pattern.findall(text):
                ver = m.strip()
                (latest_versions if ver == latest else stale_versions).add(ver)
                if ver != latest:
                    stale_titles.append(f"{ver}: {it['title'][:50]}")
        if latest_versions and stale_versions:
            conflicts_payload.append({
                "product": product_key,
                "latest": latest,
                "stale_versions": sorted(stale_versions),
                "stale_mentions": stale_titles[:5],
            })

    out_path.write_text(json.dumps({
        "stage": "gate_g08_version_consistency",
        "report_date": REPORT_DATE.isoformat(),
        "status": result.status,
        "input_count": len(items),
        "conflicts": conflicts_payload,
        "evidence": result.evidence,
        "version_registry": ctx.version_registry,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"=== gate_g08_version_consistency ===")
    print(f"status: {result.status}")
    print(f"conflicts: {len(conflicts_payload)}")
    for c in conflicts_payload:
        print(f"  · {c['product']} latest={c['latest']} stale={c['stale_versions']}")
        for sm in c["stale_mentions"][:3]:
            print(f"      {sm}")
    print(f"\nevidence trail:")
    for e in result.evidence:
        print(f"  · {e}")
    print(f"\nwrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
