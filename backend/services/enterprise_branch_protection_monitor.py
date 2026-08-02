"""
Enterprise Branch Protection Monitor
=======================================

Detects real branch-protection gaps on configured repos' default branches
via GitHub's real branch-protection API — a classic, common governance/
security finding: a "main" branch with no required reviews, no required CI
status checks, or administrators able to bypass the rules entirely, meaning
a bad or malicious change can land directly with nothing in the way.

Confirmed genuinely greenfield before building this: get_branch_protection/
update_branch_protection/remove_branch_protection already existed as GitHub
connector primitives (added for a different purpose), but grepping
backend/services/*.py found only a thin pass-through proxy in
enterprise_github_integration.py — no actual detection/remediation logic
anywhere.

Same shape as every other detector this session: check_all_repos() records
every currently-detected gap set to history (dashboard visibility), and
only a genuinely NEW gap signature for a repo+branch files a ticket via the
alert correlator. The "actually fix it" half —
enterprise_branch_protection_fix_executor.enable_minimal_protection — is
gated through the real Approval Center (backend.approval_center), since
changing a real repo's merge rules is a genuine workflow-affecting change,
unlike the side-effect-free PR the vulnerability auto-fix opens.

Deliberately does NOT add a new always-on polling loop, for the same
reason as every other monitor this session: check_all_repos() is triggered
once at app startup and via an on-demand API endpoint.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_BRANCH_PROTECTION_HISTORY_FILE = _DATA_DIR / "branch_protection_history.json"
MAX_BRANCH_PROTECTION_HISTORY = 500

BRANCH_PROTECTION_MONITORED_REPOS_ENV = "BRANCH_PROTECTION_MONITORED_REPOS"

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


def _configured_repos() -> List[Tuple[str, str]]:
    """Repos to scan, from BRANCH_PROTECTION_MONITORED_REPOS="owner/repo,owner2/repo2"."""
    raw = os.getenv(BRANCH_PROTECTION_MONITORED_REPOS_ENV, "")
    repos: List[Tuple[str, str]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part or "/" not in part:
            continue
        owner, repo = part.split("/", 1)
        repos.append((owner, repo))
    return repos


def assess_gaps(protection: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Turn a real (or absent) branch-protection response into a list of
    concrete, factual gaps — no LLM needed, this is a structural config
    check, not causal reasoning."""
    if protection is None:
        return [{
            "gap": "no_protection",
            "severity": "critical",
            "description": "No branch protection configured — anyone with write access can force-push or delete this branch.",
        }]

    gaps: List[Dict[str, str]] = []

    if not protection.get("required_pull_request_reviews"):
        gaps.append({
            "gap": "no_required_reviews",
            "severity": "high",
            "description": "No required PR review count — changes can be merged without any approval.",
        })

    checks = protection.get("required_status_checks") or {}
    contexts = checks.get("contexts") or checks.get("checks") or []
    if not checks or not contexts:
        gaps.append({
            "gap": "no_required_status_checks",
            "severity": "medium",
            "description": "No required status checks — changes can be merged without CI passing.",
        })

    enforce_admins = protection.get("enforce_admins")
    enforce_admins_enabled = enforce_admins.get("enabled", False) if isinstance(enforce_admins, dict) else bool(enforce_admins)
    if not enforce_admins_enabled:
        gaps.append({
            "gap": "admins_can_bypass",
            "severity": "medium",
            "description": "Administrators can bypass branch protection rules entirely.",
        })

    return gaps


def _overall_severity(gaps: List[Dict[str, str]]) -> str:
    if not gaps:
        return "low"
    return max((g["severity"] for g in gaps), key=lambda s: _SEVERITY_RANK.get(s, 0))


def _gap_signature(gaps: List[Dict[str, str]]) -> str:
    return "+".join(sorted(g["gap"] for g in gaps))


class BranchProtectionHistoryStore:
    """Durable record of branch-protection checks — every currently-detected
    gap set is recorded on every check (not just ticket-worthy ones) so the
    dashboard can show current governance posture per repo."""

    def __init__(self, file_path: Optional[Path] = None) -> None:
        self._file_path = file_path or _BRANCH_PROTECTION_HISTORY_FILE
        self._history: List[Dict[str, Any]] = _load_json(self._file_path)

    def last_signature(self, repo_full_name: str, branch: str) -> Optional[str]:
        for entry in self._history:
            if entry.get("repo") == repo_full_name and entry.get("branch") == branch:
                return entry.get("gap_signature")
        return None

    def record(
        self,
        repo: str,
        branch: str,
        gaps: List[Dict[str, str]],
        severity: str,
        ticket_key: Optional[str] = None,
        fix_applied: bool = False,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        entry = {
            "repo": repo,
            "branch": branch,
            "gaps": gaps,
            "gap_signature": _gap_signature(gaps),
            "severity": severity,
            "ticket_key": ticket_key,
            "fix_applied": fix_applied,
            "error": error,
            "checked_at": _now(),
        }
        self._history = [e for e in self._history if not (e.get("repo") == repo and e.get("branch") == branch)]
        self._history.insert(0, entry)
        self._history = self._history[:MAX_BRANCH_PROTECTION_HISTORY]
        _save_json(self._file_path, self._history)
        return entry

    def list_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._history[:limit]

    def clear(self) -> None:
        self._history = []
        _save_json(self._file_path, [])


branch_protection_history_store = BranchProtectionHistoryStore()


async def check_all_repos(
    history_store: Optional[BranchProtectionHistoryStore] = None,
) -> List[Dict[str, Any]]:
    """Check every configured repo's default branch for protection gaps
    once. Returns the recorded history entry for each repo checked (skips
    entirely if the github connector isn't registered, or no repos are
    configured — nothing to check, not an error)."""
    from backend.connectors.registry import connector_registry
    from backend.services.enterprise_alert_correlator import correlate_and_report
    from backend.services.enterprise_branch_protection_incident_reporter import report_branch_protection_incident

    hstore = history_store or branch_protection_history_store
    results: List[Dict[str, Any]] = []

    gh = connector_registry.get("github")
    if gh is None:
        return results

    for owner, repo in _configured_repos():
        repo_full_name = f"{owner}/{repo}"
        try:
            repo_info = await gh.get_repository(owner, repo)
            branch = repo_info.get("default_branch", "main")
        except Exception as exc:
            log.warning("Branch protection check raised for %s: %s", repo_full_name, exc)
            continue

        try:
            protection = await gh.get_branch_protection(owner, repo, branch)
        except PermissionError as exc:
            # A real, common state — GitHub's branch-protection API requires
            # a paid plan for private repos (403 "Upgrade to GitHub Pro or
            # make this repository public"). This is NOT the same as "no
            # protection configured" (a real 404), so it must not be
            # reported as a fabricated critical gap — record honestly as
            # unknown/unable-to-check instead, no ticket filed.
            log.warning("Cannot check branch protection for %s@%s: %s", repo_full_name, branch, exc)
            entry = hstore.record(repo=repo_full_name, branch=branch, gaps=[], severity="unknown", error=str(exc))
            results.append(entry)
            continue
        except Exception as exc:
            log.warning("Branch protection check raised for %s: %s", repo_full_name, exc)
            continue

        gaps = assess_gaps(protection)
        severity = _overall_severity(gaps)
        signature = _gap_signature(gaps)

        ticket_key: Optional[str] = None
        if gaps and signature != hstore.last_signature(repo_full_name, branch) and _SEVERITY_RANK.get(severity, 0) >= _SEVERITY_THRESHOLD_RANK:
            summary = "; ".join(g["description"] for g in gaps)
            issue = await correlate_and_report(
                source="branch_protection",
                service=repo_full_name,
                summary=f"{branch}: {summary}",
                reporter=lambda o=owner, r=repo, b=branch, g=gaps, s=severity: report_branch_protection_incident(o, r, b, g, s),
                severity="critical" if severity == "critical" else "warning",
            )
            ticket_key = (issue.get("key") or issue.get("ticket_key")) if issue else None

        entry = hstore.record(repo=repo_full_name, branch=branch, gaps=gaps, severity=severity, ticket_key=ticket_key)
        results.append(entry)

    return results
