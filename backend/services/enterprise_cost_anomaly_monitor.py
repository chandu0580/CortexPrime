"""
Enterprise Cost/Budget Anomaly Monitor
=========================================

Detects a real LLM-provider spend spike — a runaway loop, a misconfigured
model, or a leaked API key being abused — using the real, already-wired
cost tracking pipeline (backend.analytics.cost_engine). A common FinOps
pain point: nobody notices a spend spike until the bill arrives.

Confirmed genuinely greenfield before building this: cost_engine.py's
provider_breakdown() already existed (for the /api/costs dashboard), but
grepping backend/services/*.py found no aggregation logic anywhere that
compares a provider's current spend against its own historical baseline —
the one existing near-miss (enterprise_recommendation_engine.py's
_scan_cost_metrics) calls a get_summary() method that doesn't exist on
cost_engine and so silently never fires.

Same shape as every other detector this session: check_all_providers()
records every currently-detected gap set to history (dashboard
visibility), and only a genuinely NEW gap signature for a provider files
a ticket via the alert correlator. The "actually fix it" half —
enterprise_cost_anomaly_fix_executor.disable_provider_temporarily — is
gated through the real Approval Center, since disabling a real LLM
provider mid-operation can break real functionality if the anomaly
assessment is ever wrong, unlike a routine container restart.

Deliberately does NOT add a new always-on polling loop, for the same
reason as branch-protection/vulnerability/credential-expiry: cost
accumulates over a day, so polling every 30s like the Docker-health
watcher would just re-detect the same day's totals with no new signal.
check_all_providers() is triggered once at app startup and via an
on-demand API endpoint.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_COST_ANOMALY_HISTORY_FILE = _DATA_DIR / "cost_anomaly_history.json"
MAX_COST_ANOMALY_HISTORY = 500

# A provider's today spend must be at least this many USD before it's
# even eligible to be flagged — guards against noise on trivially small
# real numbers (e.g. $0.001 vs $0.0002 is technically "5x" but meaningless).
MIN_ABSOLUTE_USD = float(os.getenv("COST_ANOMALY_MIN_ABSOLUTE_USD", "0.50"))
# Today's spend must exceed this many multiples of the trailing 7-day
# daily average (excluding today) to count as a spike.
SPIKE_MULTIPLIER = float(os.getenv("COST_ANOMALY_SPIKE_MULTIPLIER", "3.0"))

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_SEVERITY_THRESHOLD_RANK = _SEVERITY_RANK["medium"]


def _load_json(path: Path) -> List[Dict[str, Any]]:
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception as exc:
        log.warning("Failed to load %s: %s", path.name, exc)
    return []


def _save_json(path: Path, data: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        log.warning("Failed to save %s: %s", path.name, exc)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _severity_for_multiple(multiple: float) -> str:
    if multiple >= 10:
        return "critical"
    if multiple >= 5:
        return "high"
    return "medium"


def assess_cost_anomaly(
    today_by_provider: List[Dict[str, Any]],
    trailing_by_provider: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, str]]]:
    """Turn today's real per-provider spend and a real trailing-8-day
    (today + prior 7 days) per-provider total into a per-provider gap
    list — no LLM needed, this is a structural statistical comparison,
    not causal reasoning.

    Returns {provider: [gap, ...]} for every provider present in
    today_by_provider (only providers with real spend today can have an
    anomaly; a provider with $0 today can't be "spiking").
    """
    trailing_totals = {r["provider"]: r["total_cost"] for r in trailing_by_provider}
    gaps_by_provider: Dict[str, List[Dict[str, str]]] = {}

    for entry in today_by_provider:
        provider = entry["provider"]
        today_cost = entry["total_cost"]
        gaps: List[Dict[str, str]] = []

        if today_cost >= MIN_ABSOLUTE_USD:
            trailing_total = trailing_totals.get(provider, today_cost)
            baseline_daily_avg = max(trailing_total - today_cost, 0.0) / 7

            is_spike = (
                baseline_daily_avg == 0
                or today_cost > SPIKE_MULTIPLIER * baseline_daily_avg
            )
            if is_spike:
                multiple = (
                    today_cost / baseline_daily_avg
                    if baseline_daily_avg > 0
                    else float("inf")
                )
                severity = _severity_for_multiple(multiple if multiple != float("inf") else 999)
                multiple_desc = "no prior spend" if baseline_daily_avg == 0 else f"{multiple:.1f}x its trailing average"
                gaps.append({
                    "gap": "cost_spike",
                    "severity": severity,
                    "description": (
                        f"Spend for '{provider}' today is ${today_cost:.4f} — "
                        f"{multiple_desc} (baseline ${baseline_daily_avg:.4f}/day)."
                    ),
                })

        gaps_by_provider[provider] = gaps

    return gaps_by_provider


def _overall_severity(gaps: List[Dict[str, str]]) -> str:
    if not gaps:
        return "low"
    return max((g["severity"] for g in gaps), key=lambda s: _SEVERITY_RANK.get(s, 0))


def _gap_signature(gaps: List[Dict[str, str]]) -> str:
    return "+".join(sorted(g["gap"] for g in gaps))


class CostAnomalyHistoryStore:
    """Durable record of cost-anomaly checks — every currently-detected
    gap set is recorded on every check (not just ticket-worthy ones) so
    the dashboard can show current spend-health per provider."""

    def __init__(self, file_path: Optional[Path] = None) -> None:
        self._file_path = file_path or _COST_ANOMALY_HISTORY_FILE
        self._history: List[Dict[str, Any]] = _load_json(self._file_path)

    def last_signature(self, provider: str) -> Optional[str]:
        for entry in self._history:
            if entry.get("provider") == provider:
                return entry.get("gap_signature")
        return None

    def record(
        self,
        provider: str,
        today_cost: float,
        gaps: List[Dict[str, str]],
        severity: str,
        ticket_key: Optional[str] = None,
        fix_applied: bool = False,
    ) -> Dict[str, Any]:
        entry = {
            "provider": provider,
            "today_cost": today_cost,
            "gaps": gaps,
            "gap_signature": _gap_signature(gaps),
            "severity": severity,
            "ticket_key": ticket_key,
            "fix_applied": fix_applied,
            "checked_at": _now(),
        }
        self._history = [e for e in self._history if e.get("provider") != provider]
        self._history.insert(0, entry)
        self._history = self._history[:MAX_COST_ANOMALY_HISTORY]
        _save_json(self._file_path, self._history)
        return entry

    def list_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._history[:limit]

    def clear(self) -> None:
        self._history = []
        _save_json(self._file_path, [])


cost_anomaly_history_store = CostAnomalyHistoryStore()


async def check_all_providers(
    history_store: Optional[CostAnomalyHistoryStore] = None,
) -> List[Dict[str, Any]]:
    """Check every provider with real spend today for a spend spike once.
    Returns the recorded history entry for each provider checked (skips
    entirely if there's no spend today — nothing to check, not an
    error)."""
    from backend.analytics.cost_engine import cost_engine
    from backend.services.enterprise_alert_correlator import correlate_and_report
    from backend.services.enterprise_cost_anomaly_incident_reporter import report_cost_anomaly_incident

    hstore = history_store or cost_anomaly_history_store
    results: List[Dict[str, Any]] = []

    try:
        today_by_provider = await cost_engine.provider_breakdown(days=1)
        trailing_by_provider = await cost_engine.provider_breakdown(days=8)
    except Exception as exc:
        log.warning("Cost anomaly check failed to fetch cost data: %s", exc)
        return results

    if not today_by_provider:
        return results

    try:
        gaps_by_provider = assess_cost_anomaly(today_by_provider, trailing_by_provider)
    except Exception as exc:
        log.warning("Cost anomaly assessment raised: %s", exc)
        return results

    today_cost_by_provider = {r["provider"]: r["total_cost"] for r in today_by_provider}

    for provider, gaps in gaps_by_provider.items():
        today_cost = today_cost_by_provider.get(provider, 0.0)
        severity = _overall_severity(gaps)
        signature = _gap_signature(gaps)

        ticket_key: Optional[str] = None
        if gaps and signature != hstore.last_signature(provider) and _SEVERITY_RANK.get(severity, 0) >= _SEVERITY_THRESHOLD_RANK:
            summary = "; ".join(g["description"] for g in gaps)
            issue = await correlate_and_report(
                source="cost_anomaly",
                service=provider,
                summary=summary,
                reporter=lambda p=provider, tc=today_cost, g=gaps, s=severity: report_cost_anomaly_incident(p, tc, g, s),
                severity="critical" if severity == "critical" else "warning",
            )
            ticket_key = (issue.get("key") or issue.get("ticket_key")) if issue else None

        entry = hstore.record(
            provider=provider, today_cost=today_cost, gaps=gaps, severity=severity, ticket_key=ticket_key,
        )
        results.append(entry)

    return results
