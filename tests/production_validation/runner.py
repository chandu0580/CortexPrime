"""
CortexPrime Production Validation Runner
==========================================
Orchestrates all 9 test categories, computes production scores,
and writes a structured report to disk.

Usage:
    # From project root (venv activated):
    python -m tests.production_validation.runner

    # With backend running (enables HTTP tests):
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000  # terminal 1
    python -m tests.production_validation.runner                   # terminal 2

    # Override base URL:
    VALIDATION_BASE_URL=http://staging.example.com python -m tests.production_validation.runner

Output:
    tests/production_validation/reports/validation_<timestamp>.json
    tests/production_validation/reports/validation_<timestamp>.txt
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

# ── Make project root importable ────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── Load .env ────────────────────────────────────────────────────────────────
_env_path = _ROOT / "backend" / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

from tests.production_validation import CategoryResult, backend_is_up, BASE_URL
from tests.production_validation import cat10_scoring as scoring

import tests.production_validation.cat01_long_session    as cat01
import tests.production_validation.cat02_multi_agent_stress as cat02
import tests.production_validation.cat03_voice_pipeline  as cat03
import tests.production_validation.cat04_browser_agent   as cat04
import tests.production_validation.cat05_computer_agent  as cat05
import tests.production_validation.cat06_governance      as cat06
import tests.production_validation.cat07_security        as cat07
import tests.production_validation.cat08_research        as cat08
import tests.production_validation.cat09_recovery        as cat09

# ANSI colours
_C = {
    "reset":  "\033[0m",
    "bold":   "\033[1m",
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "red":    "\033[91m",
    "cyan":   "\033[96m",
    "white":  "\033[97m",
    "grey":   "\033[90m",
}

_STATUS_COLOUR = {
    "pass":  _C["green"],
    "warn":  _C["yellow"],
    "fail":  _C["red"],
    "skip":  _C["grey"],
}


def _col(text: str, colour: str) -> str:
    return f"{_C.get(colour, '')}{text}{_C['reset']}"


def _grade_colour(grade: str) -> str:
    return {"A": "green", "B": "cyan", "C": "yellow", "D": "red"}.get(grade, "white")


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------

def _print_header():
    print()
    print(_col("═" * 70, "bold"))
    print(_col("  CortexPrime  ·  Production Validation Suite", "bold"))
    print(_col("═" * 70, "bold"))
    print(f"  Backend: {BASE_URL}")
    up = backend_is_up()
    status = _col("ONLINE",  "green") if up else _col("OFFLINE", "red")
    print(f"  Status:  {status}")
    print(_col("─" * 70, "grey"))
    print()


def _print_category(cat: CategoryResult):
    score_colour = "green" if cat.score >= 80 else "yellow" if cat.score >= 60 else "red"
    print(
        _col(f"  ► {cat.name:<40}", "bold")
        + _col(f"  {cat.score:5.1f}%", score_colour)
        + _col(f"  [{cat.passed}P / {cat.failed}F / {cat.warned}W / {cat.skipped}S]", "grey")
    )
    for c in cat.checks:
        sc    = c.status.value
        sym   = {"pass": "✓", "fail": "✗", "warn": "△", "skip": "·"}.get(sc, "?")
        col   = _STATUS_COLOUR.get(sc, "white")
        lat   = f"  {c.duration*1000:.0f}ms" if c.duration > 0 else ""
        print(
            f"    {_col(sym, col)}  {c.name:<48}"
            + _col(c.message[:60], col)
            + _col(lat, "grey")
        )
    print()


def _print_score(ps):
    print(_col("═" * 70, "bold"))
    print(_col("  PRODUCTION SCORES", "bold"))
    print(_col("─" * 70, "grey"))

    for label, val in [
        ("Reliability Score",    ps.reliability),
        ("Security Score",       ps.security),
        ("Performance Score",    ps.performance),
    ]:
        bar_len = int(val / 2)
        bar     = "█" * bar_len + "░" * (50 - bar_len)
        colour  = "green" if val >= 80 else "yellow" if val >= 60 else "red"
        print(f"  {label:<24}  {_col(f'{val:5.1f}%', colour)}  {_col(bar, colour)}")

    print(_col("─" * 70, "grey"))
    gc = _grade_colour(ps.grade)
    print(
        f"\n  {_col('COMPOSITE SCORE:', 'bold')}  "
        + _col(f"{ps.composite:.1f}%", gc)
        + f"   Grade: {_col(ps.grade, gc)}"
        + f"   {_col(ps.verdict, gc)}\n"
    )


def _print_weaknesses(ps):
    if ps.weaknesses:
        print(_col("  PRODUCTION WEAKNESSES", "bold"))
        print(_col("─" * 70, "grey"))
        for w in ps.weaknesses:
            print(f"    {_col('✗', 'red')}  {w}")
        print()

    if ps.strengths:
        print(_col("  STRENGTHS", "bold"))
        print(_col("─" * 70, "grey"))
        for s in ps.strengths:
            print(f"    {_col('✓', 'green')}  {s}")
        print()


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------

def _write_json(results: List[CategoryResult], ps, elapsed: float, report_dir: Path):
    ts   = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = report_dir / f"validation_{ts}.json"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backend_url":  BASE_URL,
        "elapsed_s":    round(elapsed, 2),
        "scores":       ps.as_dict(),
        "categories":   [c.as_dict() for c in results],
    }
    path.write_text(json.dumps(payload, indent=2))
    return path


def _write_txt(results: List[CategoryResult], ps, elapsed: float, report_dir: Path):
    ts   = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = report_dir / f"validation_{ts}.txt"
    lines = [
        "CortexPrime Production Validation Report",
        f"Generated:  {datetime.now(timezone.utc).isoformat()}",
        f"Backend:    {BASE_URL}",
        f"Duration:   {elapsed:.1f}s",
        "=" * 70,
        "",
    ]
    for cat in results:
        lines.append(f"[{cat.name}]  Score: {cat.score:.1f}%  "
                     f"P={cat.passed} F={cat.failed} W={cat.warned} S={cat.skipped}")
        for c in cat.checks:
            sym = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "skip": "SKIP"}.get(c.status.value, "???")
            lines.append(f"  {sym:<4}  {c.name:<48}  {c.message}")
        lines.append("")

    lines += [
        "=" * 70,
        "PRODUCTION SCORES",
        "-" * 70,
        f"Reliability Score:   {ps.reliability:.1f}%",
        f"Security Score:      {ps.security:.1f}%",
        f"Performance Score:   {ps.performance:.1f}%",
        "-" * 70,
        f"Composite Score:     {ps.composite:.1f}%  Grade: {ps.grade}  —  {ps.verdict}",
        "",
    ]
    if ps.weaknesses:
        lines.append("PRODUCTION WEAKNESSES")
        lines.append("-" * 70)
        for w in ps.weaknesses:
            lines.append(f"  [FAIL] {w}")
        lines.append("")
    if ps.strengths:
        lines.append("STRENGTHS")
        lines.append("-" * 70)
        for s in ps.strengths:
            lines.append(f"  [OK]   {s}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

_CATEGORIES = [
    ("01 Long Session",      cat01.run),
    ("02 Multi-Agent",       cat02.run),
    ("03 Voice",             cat03.run),
    ("04 Browser",           cat04.run),
    ("05 Computer",          cat05.run),
    ("06 Governance",        cat06.run),
    ("07 Security",          cat07.run),
    ("08 Research",          cat08.run),
    ("09 Recovery",          cat09.run),
]


def run_all() -> int:
    """Run all categories, print results, write report. Returns exit code."""
    _print_header()

    report_dir = Path("tests/production_validation/reports")
    report_dir.mkdir(parents=True, exist_ok=True)

    results: List[CategoryResult] = []
    suite_start = time.perf_counter()

    for label, runner_fn in _CATEGORIES:
        print(_col(f"  Running: {label} ...", "cyan"), end="", flush=True)
        t0  = time.perf_counter()
        cat = runner_fn()
        t1  = time.perf_counter()
        print(f"\r", end="")
        _print_category(cat)
        results.append(cat)

    elapsed = time.perf_counter() - suite_start

    # Score
    ps = scoring.compute(results)
    _print_score(ps)
    _print_weaknesses(ps)

    # Write reports
    json_path = _write_json(results, ps, elapsed, report_dir)
    txt_path  = _write_txt(results, ps, elapsed, report_dir)

    print(_col("─" * 70, "grey"))
    print(f"  Reports written to:")
    print(f"    {_col(str(json_path), 'cyan')}")
    print(f"    {_col(str(txt_path), 'cyan')}")
    print(f"  Total duration: {elapsed:.1f}s")
    print(_col("═" * 70, "bold"))
    print()

    # Exit code: 1 if any FAIL in security or if composite < 60
    any_security_fail = any(
        c.status.value == "fail"
        for cat in results if "07" in cat.name
        for c in cat.checks
    )
    if ps.composite < 60.0 or any_security_fail:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run_all())
