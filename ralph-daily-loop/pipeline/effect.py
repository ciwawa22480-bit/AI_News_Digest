"""Kleisli-style Report monad for the daily-report pipeline.

Each stage has signature: (Input, Ctx) -> Report[Output]
Stages are composed with `kleisli(*fs)` which short-circuits on FAIL,
accumulates evidence, and propagates the worst status (OK < WARN < FAIL).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Generic, Literal, TypeVar

T = TypeVar("T")
U = TypeVar("U")

Status = Literal["OK", "WARN", "FAIL"]
_RANK = {"OK": 0, "WARN": 1, "FAIL": 2}


@dataclass(frozen=True)
class Ctx:
    """Read-only context shared across the whole pipeline run.

    Replaces scattered TODAY / RECENT_DATES constants — a single source of truth.
    """
    report_date: date
    recent_window: tuple[date, ...]
    archive_index: dict[str, set[str]]    # iso_date -> set(normalized_url)
    version_registry: dict[str, str]      # product_key (lowercase) -> latest_version
    data_dir: str


@dataclass
class Report(Generic[T]):
    value: T | None
    status: Status = "OK"
    evidence: list[str] = field(default_factory=list)
    ctx: Ctx | None = None

    def bind(self, f: Callable[[T, Ctx], "Report[U]"]) -> "Report[U]":
        if self.status == "FAIL" or self.value is None:
            return Report(None, "FAIL",
                          self.evidence + ["[short-circuit] upstream FAIL"],
                          self.ctx)
        nxt = f(self.value, self.ctx)  # type: ignore[arg-type]
        merged_status: Status = max(  # type: ignore[assignment]
            (self.status, nxt.status), key=_RANK.__getitem__)
        return Report(nxt.value, merged_status,
                      self.evidence + nxt.evidence,
                      nxt.ctx or self.ctx)


def kleisli(*fs: Callable[[T, Ctx], Report[U]]):
    """Compose stages with >=> ; returns a runner that takes a seed Report."""
    def run(seed: Report) -> Report:
        r = seed
        for f in fs:
            r = r.bind(f)
        return r
    return run


def norm_url(u: str) -> str:
    return (u or "").strip().rstrip("/").lower()
