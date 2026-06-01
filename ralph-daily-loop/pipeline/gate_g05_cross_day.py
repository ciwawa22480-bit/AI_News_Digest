"""gate_g05_cross_day: Kleisli node that removes items whose URL already
appeared in the previous N days of archived reports.

Standalone runner — reads 07-merged.json, writes 07b-deduped.json and a trace.
Designed to slot into the pipeline as:

    stage7_merge_dedup >> gate_g05_cross_day >> stage8_qa_gates >> stage9_render
"""
from __future__ import annotations
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.effect import Ctx, Report, kleisli, norm_url  # noqa: E402

ARCHIVE_ROOT = Path("/data/userdata/daily-report/archive")
DATA_DIR = Path("/data/userdata/daily-report/data")

# --- Build Ctx ---------------------------------------------------------------
REPORT_DATE = date(2026, 6, 1)
LOOKBACK_DAYS = 3   # check yesterday, day-before, day-before-that


def load_archive_index(report_date: date, lookback: int) -> dict[str, set[str]]:
    """Return {iso_date: set(normalized_url)} for the past `lookback` days
    (excluding today). Reads each day's 07-merged.json — that's the
    authoritative post-dedup item set for that day's report."""
    idx: dict[str, set[str]] = {}
    for n in range(1, lookback + 1):
        d = report_date - timedelta(days=n)
        f = ARCHIVE_ROOT / d.isoformat() / "07-merged.json"
        if not f.exists():
            continue
        try:
            items = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        idx[d.isoformat()] = {norm_url(it.get("url", "")) for it in items if it.get("url")}
    return idx


# --- The Kleisli gate -------------------------------------------------------
def gate_g05_cross_day(items: list[dict], ctx: Ctx) -> Report[list[dict]]:
    prev_urls: set[str] = set().union(*ctx.archive_index.values()) if ctx.archive_index else set()
    if not prev_urls:
        return Report(items, "WARN", [f"G0.5 archive_index empty (lookback={LOOKBACK_DAYS}) — skipping"], ctx)

    kept: list[dict] = []
    dups: list[dict] = []
    for it in items:
        if norm_url(it.get("url", "")) in prev_urls:
            dups.append(it)
        else:
            kept.append(it)

    if not dups:
        return Report(kept, "OK",
                      [f"G0.5 cross-day dedup: 0 dup against {len(prev_urls)} prior URLs (lookback={LOOKBACK_DAYS}d) ✓"],
                      ctx)

    # Locate each dup back to its origin day for the evidence
    by_day: dict[str, list[str]] = {}
    for it in dups:
        nu = norm_url(it.get("url", ""))
        for d_iso, urls in ctx.archive_index.items():
            if nu in urls:
                by_day.setdefault(d_iso, []).append(it.get("title", "")[:50])
                break

    evid = [f"G0.5 cross-day dedup: removed {len(dups)} items"]
    for d_iso, titles in sorted(by_day.items(), reverse=True):
        evid.append(f"  vs {d_iso}: {len(titles)} dup → " + " | ".join(titles))

    status = "FAIL" if len(dups) >= 5 else "WARN"
    evid.append(f"  → status={status} (threshold: FAIL if ≥5)")
    return Report(kept, status, evid, ctx)


# --- Runner -----------------------------------------------------------------
def main() -> int:
    ctx = Ctx(
        report_date=REPORT_DATE,
        recent_window=tuple(REPORT_DATE - timedelta(days=i) for i in range(LOOKBACK_DAYS + 1)),
        archive_index=load_archive_index(REPORT_DATE, LOOKBACK_DAYS),
        version_registry={"claude opus": "4.8", "claude": "opus 4.8"},
        data_dir=str(DATA_DIR),
    )

    in_path = DATA_DIR / "07-merged.json"
    items = json.loads(in_path.read_text(encoding="utf-8"))

    seed = Report(items, "OK", [f"input: {in_path.name} n={len(items)}"], ctx)
    pipeline = kleisli(gate_g05_cross_day)
    result = pipeline(seed)

    # Persist
    out_path = DATA_DIR / "07b-deduped.json"
    out_path.write_text(json.dumps(result.value, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    trace_path = DATA_DIR / "07b-trace.json"
    trace_path.write_text(json.dumps({
        "stage": "gate_g05_cross_day",
        "report_date": REPORT_DATE.isoformat(),
        "lookback_days": LOOKBACK_DAYS,
        "input_count": len(items),
        "output_count": len(result.value) if result.value else 0,
        "removed": len(items) - (len(result.value) if result.value else 0),
        "status": result.status,
        "evidence": result.evidence,
        "archive_index_summary": {d: len(u) for d, u in ctx.archive_index.items()},
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"=== gate_g05_cross_day ===")
    print(f"input : {len(items)}  ->  output: {len(result.value)}  (removed {len(items) - len(result.value)})")
    print(f"status: {result.status}")
    print(f"\nevidence trail:")
    for e in result.evidence:
        print(f"  · {e}")
    print(f"\nwrote: {out_path}")
    print(f"wrote: {trace_path}")
    return 0 if result.status != "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
