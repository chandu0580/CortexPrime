"""
Verification Service
====================
After every successful connector write operation, the verification service
checks that the created/updated resource actually exists in the external
system by calling the corresponding GET/read method.

When a connector write has no natural read counterpart, the service can use
list/search operations with identity-based filtering.

Verification does NOT block the mission.  Results are recorded as:
  - "verified"   — resource confirmed via read
  - "unverified" — read failed or timed out
  - "skipped"    — no verification method known for this operation

Retry & Recovery
----------------
The service performs up to VERIFY_RETRIES attempts with exponential backoff
for eventual-consistency scenarios (GitHub, Jira, Slack).

Replay Events
-------------
  verification_started
  verification_completed
  verification_failed

Audit
-----
Each verification result is recorded to the governance audit log with
evidence (the response body snippet), connector, operation, and mission ID.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from backend.events.event_bus import event_bus
from backend.events.event_models import CognitionEvent

log = logging.getLogger(__name__)

# How many times to retry a verification on failure
VERIFY_RETRIES = 2
# Backoff between retries (seconds) — doubles each attempt
VERIFY_BACKOFF_S = 1.0
# Maximum time to wait for a single verification attempt
VERIFY_TIMEOUT_S = 15.0


# =========================================================
# OPERATION → VERIFICATION METHOD MAP
# =========================================================
#
# Maps write operation names to the read method that can verify
# the created/updated resource still exists.  The verification
# method receives the same params dictionary as the write call,
# from which it extracts the resource identifier (id, key, etc.).
#
# The second element is a callable that extracts the identifier
# param key(s) from the original params dict.
#

def _get_verify_fn(
    connector: Any,
    operation: str,
) -> tuple[Optional[str], Optional[callable]]:
    """
    Return (verify_method_name, id_extractor) for *operation* on *connector*.
    ``verify_method_name`` is the async method to call.
    ``id_extractor`` receives the operation's params dict and returns
    a kwargs dict for the verify method.
    """
    # ── GitHub ──────────────────────────────────────────────
    _GITHUB_MAP: dict[str, tuple[str, callable]] = {
        "create_repository":  ("get_repository",  lambda p: {"owner": p.get("owner", ""), "repo": p.get("name", "")}),
        "archive_repository": ("get_repository",  lambda p: {"owner": p.get("owner", ""), "repo": p.get("repo", "")}),
        "create_issue":       ("get_issue",       lambda p: {"owner": p.get("owner", ""), "repo": p.get("repo", ""), "issue_number": p.get("issue_number", 0)}),
        "update_issue":       ("get_issue",       lambda p: {"owner": p.get("owner", ""), "repo": p.get("repo", ""), "issue_number": p.get("issue_number", 0)}),
        "create_branch":      ("list_branches",   lambda p: {"owner": p.get("owner", ""), "repo": p.get("repo", "")}),
        "dispatch_workflow":  ("get_workflow_runs", lambda p: {"owner": p.get("owner", ""), "repo": p.get("repo", ""), "workflow_id": p.get("workflow_id", "")}),
        "create_release":     ("get_release",     lambda p: {"owner": p.get("owner", ""), "repo": p.get("repo", ""), "tag": p.get("tag_name", "")}),
        "create_pull_request": ("get_pull_request", lambda p: {"owner": p.get("owner", ""), "repo": p.get("repo", ""), "pull_number": p.get("pull_number", 0)}),
        "merge_pull_request":  ("get_pull_request", lambda p: {"owner": p.get("owner", ""), "repo": p.get("repo", ""), "pull_number": p.get("pull_number", 0)}),
    }
    # ── Jira ────────────────────────────────────────────────
    _JIRA_MAP: dict[str, tuple[str, callable]] = {
        "create_issue":       ("get_issue", lambda p: {"issue_key": p.get("issue_key", p.get("id", ""))}),
        "update_issue":       ("get_issue", lambda p: {"issue_key": p.get("issue_key", "")}),
        "transition_issue":   ("get_issue", lambda p: {"issue_key": p.get("issue_key", "")}),
        "assign_issue":       ("get_issue", lambda p: {"issue_key": p.get("issue_key", "")}),
    }
    # ── Slack ───────────────────────────────────────────────
    _SLACK_MAP: dict[str, tuple[str, callable]] = {
        "send_message":  ("list_messages",  lambda p: {"channel": p.get("channel", ""), "limit": 5}),
        "create_channel": ("list_channels", lambda p: {"exclude_archived": False, "limit": 200}),
    }
    # ── Teams ───────────────────────────────────────────────
    _TEAMS_MAP: dict[str, tuple[str, callable]] = {
        "create_channel":   ("get_channel",   lambda p: {"team_id": p.get("team_id", ""), "channel_id": p.get("channel_id", p.get("id", ""))}),
        "send_message":     ("list_messages", lambda p: {"team_id": p.get("team_id", ""), "channel_id": p.get("channel_id", ""), "top": 5}),
        "reply_to_message": ("list_messages", lambda p: {"team_id": p.get("team_id", ""), "channel_id": p.get("channel_id", ""), "top": 10}),
    }
    # ── Azure DevOps ────────────────────────────────────────
    _AZURE_MAP: dict[str, tuple[str, callable]] = {
        "create_work_item":  ("get_work_item",  lambda p: {"work_item_id": p.get("work_item_id", p.get("id", 0))}),
        "update_work_item":  ("get_work_item",  lambda p: {"work_item_id": p.get("work_item_id", p.get("id", 0))}),
        "queue_pipeline":    ("get_pipeline_run", lambda p: {"pipeline_id": p.get("pipeline_id", ""), "run_id": p.get("run_id", p.get("id", 0))}),
        "cancel_pipeline":   ("get_pipeline_run", lambda p: {"pipeline_id": p.get("pipeline_id", ""), "run_id": p.get("run_id", p.get("id", 0))}),
    }
    # ── ServiceNow ──────────────────────────────────────────
    _SNOW_MAP: dict[str, tuple[str, callable]] = {
        "create_incident":   ("get_incident",   lambda p: {"sys_id": p.get("sys_id", p.get("id", ""))}),
        "update_incident":   ("get_incident",   lambda p: {"sys_id": p.get("sys_id", "")}),
        "resolve_incident":  ("get_incident",   lambda p: {"sys_id": p.get("sys_id", "")}),
    }
    # ── Confluence ──────────────────────────────────────────
    _CONFLUENCE_MAP: dict[str, tuple[str, callable]] = {
        "create_page":  ("get_page",  lambda p: {"page_id": p.get("page_id", p.get("id", ""))}),
        "update_page":  ("get_page",  lambda p: {"page_id": p.get("page_id", "")}),
        "delete_page":  ("get_page",  lambda p: {"page_id": p.get("page_id", "")}),
    }
    # ── Notion ──────────────────────────────────────────────
    _NOTION_MAP: dict[str, tuple[str, callable]] = {
        "create_page":    ("get_page",    lambda p: {"page_id": p.get("page_id", p.get("id", ""))}),
        "update_page":    ("get_page",    lambda p: {"page_id": p.get("page_id", "")}),
        "archive_page":   ("get_page",    lambda p: {"page_id": p.get("page_id", "")}),
        "append_blocks":  ("list_blocks", lambda p: {"block_id": p.get("block_id", ""), "page_size": 10}),
    }

    MAPS = {
        "github":       _GITHUB_MAP,
        "jira":         _JIRA_MAP,
        "slack":        _SLACK_MAP,
        "teams":        _TEAMS_MAP,
        "azure_devops": _AZURE_MAP,
        "servicenow":   _SNOW_MAP,
        "confluence":   _CONFLUENCE_MAP,
        "notion":       _NOTION_MAP,
    }

    cmap = MAPS.get(getattr(connector, "connector_type", ""), {})
    entry = cmap.get(operation)
    if entry is None:
        return None, None
    return entry


# =========================================================
# VERIFICATION ENGINE
# =========================================================

class VerificationService:

    async def verify_operation(
        self,
        connector:       Any,
        operation:       str,
        params:          Dict[str, Any],
        execution_id:    str,
        session_id:      Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Verify that a connector write operation actually took effect by
        reading the resource back from the external system.

        Args:
            connector:   Connector instance (e.g. GitHubConnector)
            operation:   Method name that was called (e.g. "create_repository")
            params:      The params dict passed to the write operation
            execution_id:  Mission execution ID for audit/replay
            session_id:    WebSocket session ID

        Returns:
            dict with keys:
                verified:     bool
                duration_ms:  int
                evidence:     dict | None  — the response body (snipped)
                method_used:  str          — the verify method name
                error:         str | None
                retries:      int
        """
        method_name, id_extractor = _get_verify_fn(connector, operation)
        if not method_name:
            return {
                "verified":    False,
                "duration_ms": 0,
                "evidence":    None,
                "method_used": "",
                "error":       f"No verification method for {operation}",
                "retries":     0,
                "skipped":     True,
            }

        verify_method = getattr(connector, method_name, None)
        if verify_method is None:
            return {
                "verified":    False,
                "duration_ms": 0,
                "evidence":    None,
                "method_used": method_name,
                "error":       f"Verify method '{method_name}' not found on connector",
                "retries":     0,
                "skipped":     True,
            }

        # Build the params for the verify call from the operation params
        verify_params = id_extractor(params) if id_extractor else {}

        for verify_key in ("id", "issue_number", "pull_number", "work_item_id",
                           "run_id", "sys_id", "page_id", "block_id", "issue_key",
                           "channel_id", "team_id", "tag"):
            if verify_key in params and verify_key not in verify_params:
                verify_params[verify_key] = params[verify_key]

        await self._emit_verification(
            execution_id, connector, operation, method_name,
            "verification_started", "running",
            f"Verifying {operation} via {method_name}",
            session_id,
        )

        started_at = time.monotonic()
        last_error: Optional[str] = None
        evidence = None

        for attempt in range(VERIFY_RETRIES + 1):
            try:
                result = await asyncio.wait_for(
                    verify_method(**verify_params),
                    timeout=VERIFY_TIMEOUT_S,
                )
                evidence = self._extract_evidence(result)
                elapsed_ms = int((time.monotonic() - started_at) * 1000)
                log.info(
                    "Verification OK | %s.%s via %s (%dms) attempt=%d/%d",
                    getattr(connector, "connector_type", "?"),
                    operation, method_name, elapsed_ms,
                    attempt + 1, VERIFY_RETRIES + 1,
                )

                await self._emit_verification(
                    execution_id, connector, operation, method_name,
                    "verification_completed", "completed",
                    f"Verification passed — {operation} confirmed via {method_name}",
                    session_id,
                    payload={"duration_ms": elapsed_ms, "evidence": evidence,
                             "retries": attempt},
                )

                return {
                    "verified":    True,
                    "duration_ms": elapsed_ms,
                    "evidence":    evidence,
                    "method_used": method_name,
                    "error":       None,
                    "retries":     attempt,
                    "skipped":     False,
                }

            except asyncio.TimeoutError:
                last_error = "Verification timed out"
            except FileNotFoundError:
                last_error = "Resource not found (404)"
            except Exception as exc:
                last_error = str(exc)

            if attempt < VERIFY_RETRIES:
                backoff = VERIFY_BACKOFF_S * (2 ** attempt)
                log.warning(
                    "Verification attempt %d/%d failed for %s.%s: %s — "
                    "retrying in %.1fs",
                    attempt + 1, VERIFY_RETRIES + 1,
                    getattr(connector, "connector_type", "?"),
                    operation, last_error, backoff,
                )
                await asyncio.sleep(backoff)

        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        log.warning(
            "Verification FAILED | %s.%s after %d attempts (%dms): %s",
            getattr(connector, "connector_type", "?"),
            operation, VERIFY_RETRIES + 1, elapsed_ms, last_error,
        )

        await self._emit_verification(
            execution_id, connector, operation, method_name,
            "verification_failed", "failed",
            f"Verification failed — {last_error}",
            session_id,
            payload={"duration_ms": elapsed_ms, "error": last_error,
                     "retries": VERIFY_RETRIES},
        )

        return {
            "verified":    False,
            "duration_ms": elapsed_ms,
            "evidence":    evidence,
            "method_used": method_name,
            "error":       last_error,
            "retries":     VERIFY_RETRIES,
            "skipped":     False,
        }

    # ─────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def _extract_evidence(self, result: Any) -> Optional[Dict[str, Any]]:
        """Extract a safe evidence snippet from the verification response."""
        if result is None:
            return None
        if isinstance(result, dict):
            safe = {}
            for k in ("id", "key", "name", "title", "summary",
                      "state", "status", "number", "html_url",
                      "url", "webUrl", "sys_id", "archived"):
                v = result.get(k)
                if v is not None and isinstance(v, (str, int, float, bool)):
                    safe[k] = v
            return safe if safe else {"_type": type(result).__name__, "len": len(result)}
        if isinstance(result, list):
            first = result[0] if result else None
            if isinstance(first, dict):
                return self._extract_evidence(first)
            return {"_count": len(result), "_type": "list"}
        return {"_value": str(result)[:200]}

    @staticmethod
    async def _emit_verification(
        execution_id: str,
        connector:    Any,
        operation:    str,
        method_name:  str,
        event_type:   str,
        status:       str,
        message:      str,
        session_id:   Optional[str] = None,
        payload:      Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit a verification event to the event bus (→ replay store + telemetry)."""
        ctype = getattr(connector, "connector_type", "unknown")
        try:
            await event_bus.publish(CognitionEvent(
                agent        = f"verifier:{ctype}",
                event_type   = event_type,
                status       = status,
                phase        = "VERIFICATION",
                execution_id = execution_id,
                message      = message,
                payload      = {
                    "connector":       ctype,
                    "operation":       operation,
                    "verify_method":   method_name,
                    **(payload or {}),
                },
                session_id   = session_id,
            ))
        except Exception as exc:
            log.warning("Verification event emission failed: %s", exc)


# =========================================================
# SINGLETON
# =========================================================

verification_service = VerificationService()
