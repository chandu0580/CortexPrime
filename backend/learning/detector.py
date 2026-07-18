from __future__ import annotations

import logging
from typing import Any, Optional

try:
    from backend.database.repositories.factory import repo_factory as _repo_factory, RepositoryFactory
except ImportError:
    _repo_factory = None
from backend.learning.models import Pattern, PatternCategory

log = logging.getLogger(__name__)


class PatternDetector:
    def __init__(
        self,
        repo_factory: Optional[RepositoryFactory] = None,
    ) -> None:
        self._repo_factory = repo_factory or _repo_factory or RepositoryFactory()

    async def detect_all(self) -> list[Pattern]:
        patterns: list[Pattern] = []
        patterns.extend(await self._detect_repeated_failures())
        patterns.extend(await self._detect_repeated_successes())
        patterns.extend(await self._detect_connector_reliability())
        patterns.extend(await self._detect_mission_completion_trends())
        patterns.extend(await self._detect_retry_frequency())
        patterns.extend(await self._detect_approval_bottlenecks())
        patterns.extend(await self._detect_policy_violations())
        patterns.extend(await self._detect_knowledge_growth())
        return patterns

    async def detect_mission_patterns(self) -> list[Pattern]:
        patterns: list[Pattern] = []
        patterns.extend(await self._detect_repeated_failures())
        patterns.extend(await self._detect_repeated_successes())
        patterns.extend(await self._detect_mission_completion_trends())
        patterns.extend(await self._detect_retry_frequency())
        return patterns

    async def detect_execution_patterns(self) -> list[Pattern]:
        patterns: list[Pattern] = []
        patterns.extend(await self._detect_repeated_failures())
        patterns.extend(await self._detect_retry_frequency())
        return patterns

    async def detect_connector_patterns(self) -> list[Pattern]:
        return await self._detect_connector_reliability()

    async def detect_governance_patterns(self) -> list[Pattern]:
        patterns: list[Pattern] = []
        patterns.extend(await self._detect_approval_bottlenecks())
        patterns.extend(await self._detect_policy_violations())
        return patterns

    async def detect_knowledge_patterns(self) -> list[Pattern]:
        return await self._detect_knowledge_growth()

    # ------------------------------------------------------------------
    # Internal detectors
    # ------------------------------------------------------------------

    async def _detect_repeated_failures(self) -> list[Pattern]:
        patterns: list[Pattern] = []
        try:
            mission_repo = await self._repo_factory.mission_repo()
            missions = await mission_repo.list(limit=100)
            failed = [m for m in missions if m.status and m.status.lower() == "failed"]
            owner_failures: dict[str, int] = {}
            for m in failed:
                owner = m.owner or "unknown"
                owner_failures[owner] = owner_failures.get(owner, 0) + 1

            for owner, count in owner_failures.items():
                if count >= 3:
                    patterns.append(Pattern(
                        name=f"repeated_failures_{owner}",
                        description=f"Mission owner '{owner}' has {count} failed missions",
                        category=PatternCategory.MISSION.value,
                        confidence=min(count / 10, 1.0),
                        occurrences=count,
                        pattern_data={"owner": owner, "failure_count": count, "type": "repeated_failure"},
                        is_active=True,
                    ))
        except Exception as exc:
            log.warning("Failed to detect repeated failures: %s", exc)
        return patterns

    async def _detect_repeated_successes(self) -> list[Pattern]:
        patterns: list[Pattern] = []
        try:
            mission_repo = await self._repo_factory.mission_repo()
            missions = await mission_repo.list(limit=100)
            completed = [m for m in missions if m.status and m.status.lower() in ("completed", "monitoring")]
            owner_successes: dict[str, int] = {}
            for m in completed:
                owner = m.owner or "unknown"
                owner_successes[owner] = owner_successes.get(owner, 0) + 1

            for owner, count in owner_successes.items():
                if count >= 5:
                    patterns.append(Pattern(
                        name=f"repeated_successes_{owner}",
                        description=f"Mission owner '{owner}' has {count} successful missions",
                        category=PatternCategory.MISSION.value,
                        confidence=min(count / 20, 1.0),
                        occurrences=count,
                        pattern_data={"owner": owner, "success_count": count, "type": "repeated_success"},
                        is_active=True,
                    ))
        except Exception as exc:
            log.warning("Failed to detect repeated successes: %s", exc)
        return patterns

    async def _detect_connector_reliability(self) -> list[Pattern]:
        patterns: list[Pattern] = []
        try:
            conn_repo = await self._repo_factory.connector_activity_repo()
            activities = conn_repo.list if hasattr(conn_repo, "list") else None
            if activities:
                all_activities = await activities(limit=200)
                type_stats: dict[str, dict[str, int]] = {}
                for act in all_activities:
                    ctype = getattr(act, "connector_type", getattr(act, "type", "unknown"))
                    if ctype not in type_stats:
                        type_stats[ctype] = {"total": 0, "failed": 0}
                    type_stats[ctype]["total"] += 1
                    status = getattr(act, "status", "")
                    if status and status.lower() in ("failed", "error", "timeout"):
                        type_stats[ctype]["failed"] += 1

                for ctype, stats in type_stats.items():
                    if stats["total"] >= 5:
                        failure_rate = stats["failed"] / max(stats["total"], 1)
                        if failure_rate > 0.3:
                            patterns.append(Pattern(
                                name=f"connector_reliability_{ctype}",
                                description=f"Connector '{ctype}' has {failure_rate:.0%} failure rate ({stats['failed']}/{stats['total']})",
                                category=PatternCategory.CONNECTOR.value,
                                confidence=min(failure_rate * 2, 1.0),
                                occurrences=stats["failed"],
                                pattern_data={
                                    "connector_type": ctype, "total": stats["total"],
                                    "failed": stats["failed"], "failure_rate": failure_rate,
                                    "type": "connector_reliability",
                                },
                                is_active=True,
                            ))
        except Exception as exc:
            log.warning("Failed to detect connector reliability: %s", exc)
        return patterns

    async def _detect_mission_completion_trends(self) -> list[Pattern]:
        patterns: list[Pattern] = []
        try:
            mission_repo = await self._repo_factory.mission_repo()
            missions = await mission_repo.list(limit=200)
            total = len(missions)
            if total < 10:
                return patterns
            completed = len([m for m in missions if m.status and m.status.lower() in ("completed", "monitoring")])
            failed = len([m for m in missions if m.status and m.status.lower() == "failed"])
            completion_rate = completed / max(total, 1)
            failure_rate = failed / max(total, 1)

            if failure_rate > 0.4:
                patterns.append(Pattern(
                    name="high_mission_failure_rate",
                    description=f"Mission failure rate is {failure_rate:.0%} ({failed}/{total})",
                    category=PatternCategory.MISSION.value,
                    confidence=min(failure_rate * 1.5, 1.0),
                    occurrences=failed,
                    pattern_data={"total": total, "failed": failed, "completion_rate": completion_rate, "type": "completion_trend"},
                    is_active=True,
                ))
            if completion_rate > 0.9 and total >= 20:
                patterns.append(Pattern(
                    name="high_mission_completion_rate",
                    description=f"Mission completion rate is {completion_rate:.0%} ({completed}/{total})",
                    category=PatternCategory.MISSION.value,
                    confidence=min(completion_rate, 1.0),
                    occurrences=completed,
                    pattern_data={"total": total, "completed": completed, "completion_rate": completion_rate, "type": "completion_trend"},
                    is_active=True,
                ))
        except Exception as exc:
            log.warning("Failed to detect mission completion trends: %s", exc)
        return patterns

    async def _detect_retry_frequency(self) -> list[Pattern]:
        patterns: list[Pattern] = []
        try:
            exec_repo = await self._repo_factory.execution_repo()
            executions = await exec_repo.list(limit=200)
            retried = [e for e in executions if getattr(e, "error_message", None)]
            if len(retried) >= 5:
                patterns.append(Pattern(
                    name="high_retry_frequency",
                    description=f"{len(retried)} executions had errors out of {len(executions)}",
                    category=PatternCategory.EXECUTION.value,
                    confidence=min(len(retried) / 50, 1.0),
                    occurrences=len(retried),
                    pattern_data={"total": len(executions), "retried": len(retried), "type": "retry_frequency"},
                    is_active=True,
                ))
        except Exception as exc:
            log.warning("Failed to detect retry frequency: %s", exc)
        return patterns

    async def _detect_approval_bottlenecks(self) -> list[Pattern]:
        patterns: list[Pattern] = []
        try:
            approval_repo = await self._repo_factory.approval_request_repo()
            approvals = await approval_repo.list(limit=100)
            pending = [a for a in approvals if getattr(a, "status", "") == "pending"]
            if len(pending) >= 5:
                patterns.append(Pattern(
                    name="approval_bottleneck",
                    description=f"{len(pending)} pending approval requests out of {len(approvals)}",
                    category=PatternCategory.GOVERNANCE.value,
                    confidence=min(len(pending) / 20, 1.0),
                    occurrences=len(pending),
                    pattern_data={"total": len(approvals), "pending": len(pending), "type": "approval_bottleneck"},
                    is_active=True,
                ))
        except Exception as exc:
            log.warning("Failed to detect approval bottlenecks: %s", exc)
        return patterns

    async def _detect_policy_violations(self) -> list[Pattern]:
        patterns: list[Pattern] = []
        try:
            audit_repo = await self._repo_factory.audit_repo() if hasattr(self._repo_factory, "audit_repo") else None
            if audit_repo:
                audits = await audit_repo.list(limit=200)
                violations = [a for a in audits if getattr(a, "outcome", "") == "blocked"]
                if len(violations) >= 3:
                    patterns.append(Pattern(
                        name="frequent_policy_violations",
                        description=f"{len(violations)} policy violations detected",
                        category=PatternCategory.GOVERNANCE.value,
                        confidence=min(len(violations) / 20, 1.0),
                        occurrences=len(violations),
                        pattern_data={"total": len(audits), "violations": len(violations), "type": "policy_violation"},
                        is_active=True,
                    ))
        except Exception as exc:
            log.warning("Failed to detect policy violations: %s", exc)
        return patterns

    async def _detect_knowledge_growth(self) -> list[Pattern]:
        patterns: list[Pattern] = []
        try:
            knowledge_repo = await self._repo_factory.knowledge_entry_repo()
            counts = await knowledge_repo.count_by_category()
            total = sum(counts.values())
            if total >= 10:
                patterns.append(Pattern(
                    name="knowledge_growth",
                    description=f"Knowledge base has {total} entries across {len(counts)} categories",
                    category=PatternCategory.KNOWLEDGE.value,
                    confidence=min(total / 100, 1.0),
                    occurrences=total,
                    pattern_data={"total": total, "categories": counts, "type": "knowledge_growth"},
                    is_active=True,
                ))
        except Exception as exc:
            log.warning("Failed to detect knowledge growth: %s", exc)
        return patterns
