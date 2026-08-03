"""
Enterprise Watchers — continuous monitoring agents for every connector.

Each watcher polls its associated connector on a schedule, detects meaningful
events (failed pipelines, critical issues, P1 incidents, alert messages), and
emits standardized monitoring events for the rules engine to evaluate.

Reuses connector_registry for all connector operations — no duplicate auth or API logic.
"""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.connectors.registry import connector_registry
from backend.services.enterprise_event_hub import enterprise_hub

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Detected event model
# ---------------------------------------------------------------------------

class DetectedEvent:
    """A structured event detected by a watcher."""

    def __init__(
        self,
        connector_type: str,
        event_type: str,
        severity: str,
        title: str,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.connector_type = connector_type
        self.event_type = event_type
        self.severity = severity
        self.title = title
        self.description = description
        self.metadata = metadata or {}
        self.detected_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connector_type": self.connector_type,
            "event_type": self.event_type,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "metadata": self.metadata,
            "detected_at": self.detected_at,
        }


# ---------------------------------------------------------------------------
# Safe connector call helper
# ---------------------------------------------------------------------------

async def _safe_call(connector: Any, method_name: str, *args, **kwargs) -> Any:
    """Safely call a connector method, returning None if it doesn't exist or fails."""
    method = getattr(connector, method_name, None)
    if method is None:
        return None
    try:
        if asyncio.iscoroutinefunction(method):
            return await method(*args, **kwargs)
        return method(*args, **kwargs)
    except Exception as exc:
        log.debug("Connector call %s.%s failed: %s", connector.connector_type, method_name, exc)
        return None


async def evaluate_event_against_rules(event: Dict[str, Any]) -> Dict[str, int]:
    """Record a detected event, evaluate it against monitoring rules, and
    auto-create a mission for any matching rule with auto_create_mission=True.

    Shared by the continuous poll loop (WatcherManager._poll_loop) and the
    manual POST /api/monitoring/poll endpoint, so both paths actually
    trigger the same rule-driven automation — previously only the manual
    endpoint did; the background loop detected events and streamed them to
    the UI event feed, but never evaluated them against rules at all.
    """
    from backend.services.autonomous_mission_generator import auto_mission_generator
    from backend.services.monitoring_rules_engine import monitoring_rules

    monitoring_rules.record_event(event)
    matching_rules = await monitoring_rules.evaluate_event(event)
    missions_created = 0
    for rule in matching_rules:
        if rule.auto_create_mission:
            result = await auto_mission_generator.create_mission(rule, event)
            if result:
                missions_created += 1
    return {"rules_matched": len(matching_rules), "missions_created": missions_created}


# ---------------------------------------------------------------------------
# Base watcher
# ---------------------------------------------------------------------------

class EnterpriseWatcher(ABC):
    """Base class for enterprise connector watchers."""

    connector_type: str = ""
    poll_interval: int = 120  # seconds between polls
    _running: bool = False
    _task: Optional[asyncio.Task] = None

    async def initialize(self) -> bool:
        """Prepare the watcher for operation. Returns True if ready."""
        connector = connector_registry.get(self.connector_type)
        if connector is None:
            log.warning("Watcher %s: connector not registered", self.connector_type)
            return False
        health = await _safe_call(connector, "health")
        available = health is not None and (isinstance(health, dict) and health.get("status") != "error")
        if available:
            log.info("Watcher %s initialized — poll interval %ds", self.connector_type, self.poll_interval)
        else:
            log.warning("Watcher %s: connector health check failed", self.connector_type)
        return available

    async def shutdown(self) -> None:
        """Stop the watcher and cancel its poll task."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self._task = None
        log.info("Watcher %s shutdown", self.connector_type)

    async def health(self) -> Dict[str, Any]:
        """Return watcher health status."""
        connector = connector_registry.get(self.connector_type)
        health_result: Dict[str, Any] = {"status": "unknown", "available": False}
        if connector:
            result = await _safe_call(connector, "health")
            if result:
                health_result = result if isinstance(result, dict) else {"status": str(result), "available": True}
                health_result["available"] = True
        return {
            "connector": self.connector_type,
            "running": self._running,
            "poll_interval": self.poll_interval,
            **health_result,
        }

    @abstractmethod
    async def poll(self) -> List[DetectedEvent]:
        """Poll the connector for events. Returns a list of detected events."""

    async def process_event(self, event: DetectedEvent) -> None:
        """Emit a monitoring event for a detected event."""
        await enterprise_hub.emit_monitoring_event_detected(
            connector_type=self.connector_type,
            event_title=event.title,
            severity=event.severity,
            event_data=event.to_dict(),
        )

    def _get_connector(self) -> Any:
        """Get the connector instance from the registry."""
        return connector_registry.get(self.connector_type)


# ---------------------------------------------------------------------------
# GitHub Watcher
# ---------------------------------------------------------------------------

class GitHubWatcher(EnterpriseWatcher):
    connector_type = "github"
    poll_interval = 90

    async def poll(self) -> List[DetectedEvent]:
        events: List[DetectedEvent] = []
        connector = self._get_connector()
        if not connector:
            return events

        repos = await _safe_call(connector, "list_repositories")
        if not repos or not isinstance(repos, list):
            return events

        for repo in repos[:5]:
            repo_name = repo.get("name", repo.get("full_name", "unknown"))
            owner = repo.get("owner", {}).get("login") or repo.get("owner") or "unknown"
            if not isinstance(owner, str):
                continue

            # Check workflow runs for failures
            runs = await _safe_call(connector, "get_workflow_runs", owner=owner, repo=repo_name, workflow_id="all")
            if runs and isinstance(runs, list):
                for run in runs[:3]:
                    if run.get("conclusion") == "failure" or run.get("status") == "failure":
                        events.append(DetectedEvent(
                            connector_type="github",
                            event_type="pipeline_failure",
                            severity="critical",
                            title=f"Pipeline failed: {run.get('name', 'unknown')} in {repo_name}",
                            description=f"Workflow {run.get('workflow_id', '?')} run {run.get('id', '?')} failed",
                            metadata={"repo": repo_name, "run_id": run.get("id"), "owner": owner},
                        ))

            # Check open issues for critical labels
            issues = await _safe_call(connector, "list_pull_requests", owner=owner, repo=repo_name, state="open")
            if issues and isinstance(issues, list):
                for issue in issues[:5]:
                    labels = [label.get("name", "") if isinstance(label, dict) else str(label) for label in (issue.get("labels") or [])]
                    critical_keywords = ["bug", "critical", "p1", "blocker", "security"]
                    if any(kw in label.lower() for label in labels for kw in critical_keywords):
                        events.append(DetectedEvent(
                            connector_type="github",
                            event_type="critical_issue",
                            severity="high",
                            title=f"Critical issue: {issue.get('title', 'Untitled')} in {repo_name}",
                            description=f"Issue #{issue.get('number')} has critical labels: {labels}",
                            metadata={"repo": repo_name, "issue_number": issue.get("number")},
                        ))

        return events


# ---------------------------------------------------------------------------
# Jira Watcher
# ---------------------------------------------------------------------------

class JiraWatcher(EnterpriseWatcher):
    connector_type = "jira"
    poll_interval = 120

    async def poll(self) -> List[DetectedEvent]:
        events: List[DetectedEvent] = []
        connector = self._get_connector()
        if not connector:
            return events

        # Jira only supports get_issue — poll checks configured watched issues
        watched_issues = getattr(self, "_watched_issues", [])
        for issue_key in watched_issues:
            issue = await _safe_call(connector, "get_issue", issue_key=issue_key)
            if not issue or not isinstance(issue, dict):
                continue
            priority = (issue.get("fields") or {}).get("priority", {}).get("name", "")
            status = (issue.get("fields") or {}).get("status", {}).get("name", "")
            if "critical" in priority.lower() or "blocker" in priority.lower():
                events.append(DetectedEvent(
                    connector_type="jira",
                    event_type="critical_issue",
                    severity="critical",
                    title=f"Critical Jira issue: {issue.get('key', issue_key)}",
                    description=f"{issue.get('fields', {}).get('summary', '')} — Status: {status}",
                    metadata={"issue_key": issue_key, "priority": priority, "status": status},
                ))

        return events


# ---------------------------------------------------------------------------
# Slack Watcher
# ---------------------------------------------------------------------------

class SlackWatcher(EnterpriseWatcher):
    connector_type = "slack"
    poll_interval = 60

    async def poll(self) -> List[DetectedEvent]:
        events: List[DetectedEvent] = []
        connector = self._get_connector()
        if not connector:
            return events

        channels = await _safe_call(connector, "list_channels", exclude_archived=True, limit=50)
        if not channels or not isinstance(channels, list):
            return events

        alert_keywords = ["alert", "incident", "p1", "critical", "outage", "failed", "down", "emergency"]
        for channel in channels[:10]:
            channel_id = channel.get("id") or channel.get("name", "")
            if not channel_id:
                continue
            messages = await _safe_call(connector, "list_messages", channel=channel_id, limit=20)
            if not messages or not isinstance(messages, list):
                continue
            for msg in messages[:5]:
                text = msg.get("text", "") or msg.get("message", "")
                if any(kw in text.lower() for kw in alert_keywords):
                    events.append(DetectedEvent(
                        connector_type="slack",
                        event_type="alert_message",
                        severity="high",
                        title=f"Alert in #{channel.get('name', channel_id)}",
                        description=text[:200],
                        metadata={"channel": channel.get("name"), "channel_id": channel_id,
                                  "ts": msg.get("ts")},
                    ))

        return events


# ---------------------------------------------------------------------------
# Teams Watcher
# ---------------------------------------------------------------------------

class TeamsWatcher(EnterpriseWatcher):
    connector_type = "teams"
    poll_interval = 90

    async def poll(self) -> List[DetectedEvent]:
        events: List[DetectedEvent] = []
        connector = self._get_connector()
        if not connector:
            return events

        teams = await _safe_call(connector, "list_teams")
        if not teams or not isinstance(teams, list):
            return events

        alert_keywords = ["alert", "incident", "p1", "critical", "outage", "failed", "down"]
        for team in teams[:3]:
            team_id = team.get("id") or team.get("team_id", "")
            if not team_id:
                continue
            channels = await _safe_call(connector, "list_channels", team_id=team_id)
            if not channels or not isinstance(channels, list):
                continue
            for channel in channels[:5]:
                channel_id = channel.get("id") or channel.get("channel_id", "")
                if not channel_id:
                    continue
                messages = await _safe_call(connector, "list_messages", team_id=team_id, channel_id=channel_id, top=20)
                if not messages or not isinstance(messages, list):
                    continue
                for msg in messages[:5]:
                    text = msg.get("body", "") or msg.get("content", "") or msg.get("text", "")
                    if any(kw in text.lower() for kw in alert_keywords):
                        events.append(DetectedEvent(
                            connector_type="teams",
                            event_type="alert_message",
                            severity="high",
                            title=f"Alert in {team.get('displayName', team_id)}/{channel.get('displayName', channel_id)}",
                            description=text[:200],
                            metadata={"team": team.get("displayName"), "channel": channel.get("displayName")},
                        ))

        return events


# ---------------------------------------------------------------------------
# Azure DevOps Watcher
# ---------------------------------------------------------------------------

class AzureDevOpsWatcher(EnterpriseWatcher):
    connector_type = "azure_devops"
    poll_interval = 90

    async def poll(self) -> List[DetectedEvent]:
        events: List[DetectedEvent] = []
        connector = self._get_connector()
        if not connector:
            return events

        # Check pipeline failures
        pipelines = await _safe_call(connector, "list_pipelines")
        if pipelines and isinstance(pipelines, list):
            for pipeline in pipelines[:10]:
                pipeline_id = pipeline.get("id")
                if pipeline_id:
                    run_id = pipeline.get("latestRun", {}).get("id") if isinstance(pipeline.get("latestRun"), dict) else None
                    if run_id:
                        run = await _safe_call(connector, "get_pipeline_run", pipeline_id=pipeline_id, run_id=run_id)
                        if run and isinstance(run, dict) and run.get("result") == "failed":
                            events.append(DetectedEvent(
                                connector_type="azure_devops",
                                event_type="pipeline_failure",
                                severity="critical",
                                title=f"Azure Pipeline failed: {pipeline.get('name', 'unknown')}",
                                description=f"Run {run_id} result: failed",
                                metadata={"pipeline_id": pipeline_id, "run_id": run_id,
                                          "pipeline_name": pipeline.get("name")},
                            ))

        # Check critical work items
        wiql = "SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.Priority] = 1 AND [System.State] <> 'Done' AND [System.State] <> 'Closed'"
        wi_result = await _safe_call(connector, "list_work_items", query=wiql)
        if wi_result and isinstance(wi_result, dict):
            work_items = wi_result.get("workItems", wi_result.get("value", []))
            if isinstance(work_items, list):
                for wi in work_items[:10]:
                    wi_id = wi.get("id") or wi.get("workItemId")
                    if wi_id:
                        detail = await _safe_call(connector, "get_work_item", work_item_id=int(wi_id))
                        if detail and isinstance(detail, dict):
                            fields = detail.get("fields") or detail
                            title = fields.get("System.Title", fields.get("title", f"Work item {wi_id}"))
                            events.append(DetectedEvent(
                                connector_type="azure_devops",
                                event_type="critical_work_item",
                                severity="high",
                                title=f"Critical work item: {title}",
                                description=f"Priority 1 item #{wi_id}",
                                metadata={"work_item_id": wi_id, "title": title},
                            ))

        return events


# ---------------------------------------------------------------------------
# ServiceNow Watcher
# ---------------------------------------------------------------------------

class ServiceNowWatcher(EnterpriseWatcher):
    connector_type = "servicenow"
    poll_interval = 60

    async def poll(self) -> List[DetectedEvent]:
        events: List[DetectedEvent] = []
        connector = self._get_connector()
        if not connector:
            return events

        # Check P1 incidents
        p1_incidents = await _safe_call(connector, "list_incidents",
                                         sysparm_query="priority=1^state!=6^state!=7",
                                         sysparm_limit=20)
        if p1_incidents and isinstance(p1_incidents, list):
            for inc in p1_incidents:
                events.append(DetectedEvent(
                    connector_type="servicenow",
                    event_type="p1_incident",
                    severity="critical",
                    title=f"P1 Incident: {inc.get('short_description', 'Untitled')}",
                    description=f"Incident {inc.get('sys_id', '?')} — Priority 1",
                    metadata={"sys_id": inc.get("sys_id"), "number": inc.get("number"),
                              "state": inc.get("state")},
                ))

        # Check P2 incidents
        p2_incidents = await _safe_call(connector, "list_incidents",
                                         sysparm_query="priority=2^state!=6^state!=7",
                                         sysparm_limit=20)
        if p2_incidents and isinstance(p2_incidents, list):
            for inc in p2_incidents[:5]:
                events.append(DetectedEvent(
                    connector_type="servicenow",
                    event_type="high_incident",
                    severity="high",
                    title=f"P2 Incident: {inc.get('short_description', 'Untitled')}",
                    description=f"Incident {inc.get('sys_id', '?')} — Priority 2",
                    metadata={"sys_id": inc.get("sys_id"), "number": inc.get("number")},
                ))

        return events


# ---------------------------------------------------------------------------
# Confluence Watcher
# ---------------------------------------------------------------------------

class ConfluenceWatcher(EnterpriseWatcher):
    connector_type = "confluence"
    poll_interval = 180

    async def poll(self) -> List[DetectedEvent]:
        events: List[DetectedEvent] = []
        connector = self._get_connector()
        if not connector:
            return events

        # Check recent page changes via CQL
        recent = await _safe_call(connector, "search_pages",
                                   cql="type=page order by lastmodified desc",
                                   limit=10)
        if recent and isinstance(recent, dict):
            pages = recent.get("results", [])
            if isinstance(pages, list):
                for page in pages:
                    title = page.get("title", "Untitled")
                    version = page.get("version", {}).get("number", 1) if isinstance(page.get("version"), dict) else 1
                    if version and int(str(version)) > 1:
                        events.append(DetectedEvent(
                            connector_type="confluence",
                            event_type="page_updated",
                            severity="low",
                            title=f"Page updated: {title}",
                            description=f"Version {version}",
                            metadata={"page_id": page.get("id"), "title": title, "version": version},
                        ))

        return events


# ---------------------------------------------------------------------------
# Notion Watcher
# ---------------------------------------------------------------------------

class NotionWatcher(EnterpriseWatcher):
    connector_type = "notion"
    poll_interval = 180

    async def poll(self) -> List[DetectedEvent]:
        events: List[DetectedEvent] = []
        connector = self._get_connector()
        if not connector:
            return events

        # Search for recently updated pages
        result = await _safe_call(connector, "search", query="", page_size=20)
        if result and isinstance(result, dict):
            pages = result.get("results", [])
            if isinstance(pages, list):
                for page in pages[:10]:
                    title = ""
                    props = page.get("properties") or {}
                    for prop in props.values():
                        if isinstance(prop, dict) and prop.get("type") == "title":
                            title_parts = prop.get("title", [])
                            if title_parts:
                                title = "".join(t.get("plain_text", "") for t in title_parts)
                            break
                    if not title:
                        title = page.get("id", "Untitled")
                    events.append(DetectedEvent(
                        connector_type="notion",
                        event_type="page_updated",
                        severity="low",
                        title=f"Notion page updated: {title}",
                        description=f"Page {page.get('id', '?')}",
                        metadata={"page_id": page.get("id"), "title": title},
                    ))

        return events


# ---------------------------------------------------------------------------
# Docker Container Health Watcher
# ---------------------------------------------------------------------------

class DockerHealthWatcher(EnterpriseWatcher):
    """Unlike the other watchers here (generic connector-event polling that
    feeds the monitoring_rules auto-mission pipeline), poll() also runs the
    real detect -> Jira-ticket -> gated-fix loop directly via
    enterprise_docker_health_monitor.check_all_containers() — the same
    check_all_repos()-style detector every other domain (branch-protection,
    vulnerability, etc.) uses, just wired continuously instead of one-shot
    since a crash-looping container is time-sensitive. The DetectedEvents
    returned below are only for the generic WebSocket/monitoring-rules feed
    on top of that — the ticket-filing already happened inside check_all_containers().
    """
    connector_type = "docker"
    poll_interval = 30

    async def poll(self) -> List[DetectedEvent]:
        from backend.services.enterprise_docker_health_monitor import check_all_containers

        events: List[DetectedEvent] = []
        try:
            results = await check_all_containers()
        except Exception as exc:
            log.debug("Docker health check failed: %s", exc)
            return events

        for entry in results:
            if not entry.get("gaps"):
                continue
            events.append(DetectedEvent(
                connector_type="docker",
                event_type="container_health_gap",
                severity=entry.get("severity", "warning"),
                title=f"Container health gap: {entry.get('container', 'unknown')}",
                description="; ".join(g["description"] for g in entry["gaps"]),
                metadata={
                    "container": entry.get("container"),
                    "container_id": entry.get("container_id"),
                    "gaps": entry.get("gaps"),
                    "ticket_key": entry.get("ticket_key"),
                },
            ))

        return events


# ---------------------------------------------------------------------------
# Watcher Manager
# ---------------------------------------------------------------------------

_WATCHER_CLASSES: List[type] = [
    GitHubWatcher,
    JiraWatcher,
    SlackWatcher,
    TeamsWatcher,
    AzureDevOpsWatcher,
    ServiceNowWatcher,
    ConfluenceWatcher,
    NotionWatcher,
    DockerHealthWatcher,
]


class WatcherManager:
    """Manages the lifecycle and scheduling of all enterprise watchers."""

    def __init__(self) -> None:
        self._watchers: Dict[str, EnterpriseWatcher] = {}
        self._initialized = False

    def _build_watchers(self) -> None:
        """Instantiate all watcher classes."""
        for cls in _WATCHER_CLASSES:
            watcher = cls()
            self._watchers[watcher.connector_type] = watcher

    async def initialize_all(self) -> Dict[str, bool]:
        """Initialize all watchers. Returns {connector_type: success}."""
        self._build_watchers()

        results: Dict[str, bool] = {}
        for ct, watcher in self._watchers.items():
            try:
                ok = await watcher.initialize()
                results[ct] = ok
            except Exception as exc:
                log.warning("Watcher %s init failed: %s", ct, exc)
                results[ct] = False

        self._initialized = True
        ready = sum(1 for v in results.values() if v)
        log.info("WatcherManager initialized — %d/%d watchers ready", ready, len(self._watchers))
        return results

    async def shutdown_all(self) -> None:
        """Shut down all watchers."""
        for ct, watcher in self._watchers.items():
            try:
                await watcher.shutdown()
            except Exception as exc:
                log.debug("Watcher %s shutdown: %s", ct, exc)
        self._initialized = False
        log.info("WatcherManager shutdown complete")

    async def health_all(self) -> Dict[str, Any]:
        """Return health status for all watchers."""
        return {
            ct: await watcher.health()
            for ct, watcher in self._watchers.items()
        }

    async def start_polling(self) -> None:
        """Start continuous polling for all initialized watchers."""
        tasks = []
        for ct, watcher in self._watchers.items():
            task = asyncio.create_task(self._poll_loop(watcher), name=f"watcher-{ct}")
            tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _poll_loop(self, watcher: EnterpriseWatcher) -> None:
        """Continuous poll loop for a single watcher."""
        # Without this, EnterpriseWatcher.shutdown()'s cancellation logic
        # (keyed on self._task) has nothing to cancel — start_polling()
        # creates this loop as a Task but never stored it anywhere, so
        # shutdown_all() silently cancelled nothing.
        watcher._task = asyncio.current_task()
        watcher._running = True
        while watcher._running:
            try:
                events = await watcher.poll()
                for event in events:
                    await watcher.process_event(event)
                    try:
                        await evaluate_event_against_rules(event.to_dict())
                    except Exception as exc:
                        log.debug("Rule evaluation failed for watcher %s event: %s", watcher.connector_type, exc)
                if events:
                    log.info(
                        "Watcher %s detected %d event(s)",
                        watcher.connector_type, len(events),
                    )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.debug("Watcher %s poll error: %s", watcher.connector_type, exc)

            await asyncio.sleep(watcher.poll_interval)

    async def poll_once(self, connector_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Poll specified or all watchers once. Returns detected events."""
        all_events: List[Dict[str, Any]] = []
        watchers_to_poll = (
            [self._watchers[connector_type]] if connector_type and connector_type in self._watchers
            else list(self._watchers.values())
        )

        for watcher in watchers_to_poll:
            try:
                events = await watcher.poll()
                for event in events:
                    await watcher.process_event(event)
                    all_events.append(event.to_dict())
            except Exception as exc:
                log.debug("Poll-once %s failed: %s", watcher.connector_type, exc)

        return all_events

    @property
    def watchers(self) -> Dict[str, EnterpriseWatcher]:
        return self._watchers


# Singleton
watcher_manager = WatcherManager()
