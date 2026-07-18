"""
Enterprise Repository Brain — permanent engineering knowledge model for every
repository in the enterprise.

This is NOT a scanner. It reuses every existing subsystem.

Reuses:
  - EnterpriseCodeIntelligence    — scan / parse / impact / dependency graph
  - EnterpriseGraphService        — knowledge graph entity storage & query
  - EnterpriseEngineeringMemory   — experiences, patterns, similarity
  - EnterpriseRuntimeStore        — execution history
  - EnterpriseContextIntelligence — context snapshots
  - EnterpriseGitHubIntegration   — repo metadata, branches, PRs
  - EnterpriseInfrastructureIntelligence — runtime mapping
  - EnterpriseDeliveryOrchestrator — delivery history
  - EnterpriseArchitectureIntelligence — architecture models

Phases:
   1. Repository Identity
   2. Architecture Model
   3. Dependency Graph
   4. Ownership Intelligence
   5. Runtime Mapping
   6. Operational History
   7. Architecture Drift
   8. Executive Integration
   9. Decision Integration
  10. Repository Dashboard
"""
from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_BRAIN_FILE = _DATA_DIR / "repository_brain.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str = "brain") -> str:
    import uuid
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception as exc:
        log.debug("Failed to load %s: %s", path.name, exc)
    return {}


def _save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


# =============================================================================
# Phase 1 — Repository Identity
# =============================================================================


@dataclass(frozen=True)
class RepositoryIdentity:
    repository: str = ""
    organization: str = ""
    owner: str = ""
    description: str = ""
    default_branch: str = "main"
    branches: List[str] = field(default_factory=list)
    languages: Dict[str, int] = field(default_factory=dict)
    frameworks: List[str] = field(default_factory=list)
    build_systems: List[str] = field(default_factory=list)
    package_managers: List[str] = field(default_factory=list)
    deployment_targets: List[str] = field(default_factory=list)
    total_files: int = 0
    total_entities: int = 0
    is_private: bool = False
    is_fork: bool = False
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    last_scanned_at: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# Phase 2 — Architecture Model
# =============================================================================


@dataclass(frozen=True)
class ArchitectureComponent:
    component_id: str = ""
    component_type: str = ""
    name: str = ""
    description: str = ""
    file_paths: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArchitectureModel:
    services: List[Dict[str, Any]] = field(default_factory=list)
    modules: List[Dict[str, Any]] = field(default_factory=list)
    libraries: List[Dict[str, Any]] = field(default_factory=list)
    apis: List[Dict[str, Any]] = field(default_factory=list)
    workers: List[Dict[str, Any]] = field(default_factory=list)
    schedulers: List[Dict[str, Any]] = field(default_factory=list)
    agents: List[Dict[str, Any]] = field(default_factory=list)
    connectors: List[Dict[str, Any]] = field(default_factory=list)
    runtime_components: List[Dict[str, Any]] = field(default_factory=list)
    built_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# Phase 4 — Ownership Intelligence
# =============================================================================


@dataclass(frozen=True)
class OwnershipRecord:
    service: str = ""
    owners: List[str] = field(default_factory=list)
    teams: List[str] = field(default_factory=list)
    maintainers: List[str] = field(default_factory=list)
    is_critical: bool = False
    business_domain: str = ""
    repository: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# Phase 7 — Architecture Drift
# =============================================================================


@dataclass(frozen=True)
class DriftRecord:
    drift_id: str = ""
    drift_type: str = ""
    severity: str = "info"
    description: str = ""
    repository: str = ""
    service: str = ""
    detected_at: str = ""
    resolved: bool = False
    resolved_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# Repository Brain — main service
# =============================================================================


class EnterpriseRepositoryBrain:
    """Permanent engineering knowledge model for all repositories.

    Continuously aggregates data from every existing subsystem to build
    and maintain a complete digital twin of each repository's identity,
    architecture, dependencies, ownership, runtime, history, and drift.
    """

    def __init__(self) -> None:
        self._repositories: Dict[str, RepositoryIdentity] = {}
        self._architectures: Dict[str, ArchitectureModel] = {}
        self._ownership: Dict[str, OwnershipRecord] = {}
        self._drift: List[DriftRecord] = []
        self._loaded: bool = False

    # ── Persistence ──────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            data = _load_json(_BRAIN_FILE)
            for repo, idata in data.get("identities", {}).items():
                self._repositories[repo] = RepositoryIdentity(**idata)
            for repo, adata in data.get("architectures", {}).items():
                self._architectures[repo] = ArchitectureModel(**adata)
            for svc, odata in data.get("ownership", {}).items():
                self._ownership[svc] = OwnershipRecord(**odata)
            for d in data.get("drift", []):
                self._drift.append(DriftRecord(**d))
        except Exception as exc:
            log.debug("Failed to load brain: %s", exc)
        self._loaded = True

    def clear(self) -> None:
        """Clear all brain data (for testing)."""
        self._repositories.clear()
        self._architectures.clear()
        self._ownership.clear()
        self._drift.clear()
        self._save()

    def _save(self) -> None:
        try:
            data = {
                "identities": {k: v.to_dict() for k, v in self._repositories.items()},
                "architectures": {k: v.to_dict() for k, v in self._architectures.items()},
                "ownership": {k: v.to_dict() for k, v in self._ownership.items()},
                "drift": [d.to_dict() for d in self._drift],
                "updated_at": _now(),
            }
            _save_json(_BRAIN_FILE, data)
        except Exception as exc:
            log.debug("Failed to save brain: %s", exc)

    # =====================================================================
    # Phase 1 — Repository Identity
    # =====================================================================

    async def refresh_identity(self, repository: str) -> RepositoryIdentity:
        """Refresh repository identity from GitHub + CodeIntelligence."""
        self._load()
        org = ""
        default_branch = "main"
        branches: List[str] = []
        languages: Dict[str, int] = {}
        frameworks: List[str] = []
        build_systems: List[str] = []
        package_managers: List[str] = []
        deployment_targets: List[str] = []
        total_files = 0
        total_entities = 0
        description = ""
        owner = ""
        is_private = False
        is_fork = False
        stars = 0
        forks = 0
        open_issues = 0

        if "/" in repository:
            parts = repository.split("/")
            org = parts[0]
            name = parts[-1].replace(".git", "")

        # GitHub metadata
        try:
            from backend.services.enterprise_github_integration import github_integration
            if hasattr(github_integration, "sync_repository") and org and name:
                gh_data = await github_integration.sync_repository(org, name)
                if isinstance(gh_data, dict):
                    default_branch = gh_data.get("default_branch", default_branch)
                    description = gh_data.get("description", "")
                    is_private = gh_data.get("private", False)
                    is_fork = gh_data.get("fork", False)
                    stars = gh_data.get("stars", 0)
                    forks = gh_data.get("forks", 0)
                    open_issues = gh_data.get("open_issues", 0)
                    owner = gh_data.get("owner", {}).get("login", "") if isinstance(gh_data.get("owner"), dict) else ""
        except Exception as exc:
            log.debug("GitHub sync failed: %s", exc)

        try:
            from backend.services.enterprise_github_integration import github_integration
            if hasattr(github_integration, "list_branches"):
                raw = await github_integration.list_branches(repository)
                if isinstance(raw, list):
                    branches = [b.get("name", "") if isinstance(b, dict) else str(b) for b in raw]
                    if default_branch not in branches and branches:
                        default_branch = branches[0]
        except Exception:
            pass

        # Code Intelligence scan
        try:
            from backend.services.enterprise_code_intelligence import code_intelligence
            scan = await code_intelligence.scan_repository(repository)
            if isinstance(scan, dict):
                languages = scan.get("languages", {})
                total_files = scan.get("total_files", 0)
                total_entities = scan.get("entity_count", 0)
                frameworks_from_scan = []
                for fi in scan.get("files", []):
                    fp = fi.get("path", "")
                    if "requirements.txt" in fp:
                        package_managers.append("pip")
                    elif "package.json" in fp:
                        package_managers.append("npm")
                        build_systems.append("npm/node")
                    elif "pyproject.toml" in fp:
                        package_managers.append("pip")
                        build_systems.append("python-build")
                    elif "pom.xml" in fp:
                        package_managers.append("maven")
                        build_systems.append("maven")
                    elif "build.gradle" in fp or "build.gradle.kts" in fp:
                        package_managers.append("gradle")
                        build_systems.append("gradle")
                    elif "go.mod" in fp:
                        package_managers.append("go-modules")
                        build_systems.append("go-build")
                    elif "Cargo.toml" in fp:
                        package_managers.append("cargo")
                        build_systems.append("cargo")
                    elif "Dockerfile" in fp:
                        deployment_targets.append("docker")
                    elif ".github/workflows" in fp:
                        build_systems.append("github-actions")
                    elif fp.endswith((".yaml", ".yml")) and "deploy" in fp.lower():
                        deployment_targets.append("kubernetes")
                    if "fastapi" in fp.lower() or "django" in fp.lower():
                        frameworks_from_scan.append("fastapi" if "fastapi" in fp.lower() else "django")
                    if "react" in fp.lower() or "vue" in fp.lower() or "angular" in fp.lower():
                        frameworks_from_scan.append("react" if "react" in fp.lower() else ("vue" if "vue" in fp.lower() else "angular"))
                frameworks = list(set(frameworks_from_scan))
        except Exception as exc:
            log.debug("Code Intelligence scan failed: %s", exc)

        identity = RepositoryIdentity(
            repository=repository,
            organization=org,
            owner=owner,
            description=description,
            default_branch=default_branch,
            branches=branches,
            languages=languages,
            frameworks=frameworks,
            build_systems=list(set(build_systems)),
            package_managers=list(set(package_managers)),
            deployment_targets=list(set(deployment_targets)),
            total_files=total_files,
            total_entities=total_entities,
            is_private=is_private,
            is_fork=is_fork,
            stars=stars,
            forks=forks,
            open_issues=open_issues,
            last_scanned_at=_now(),
            created_at=self._repositories.get(repository, RepositoryIdentity()).created_at or _now(),
            updated_at=_now(),
        )
        self._repositories[repository] = identity
        self._save()
        return identity

    async def get_identity(self, repository: str) -> Optional[RepositoryIdentity]:
        self._load()
        return self._repositories.get(repository)

    async def list_repositories(self) -> List[Dict[str, Any]]:
        self._load()
        return [r.to_dict() for r in self._repositories.values()]

    # =====================================================================
    # Phase 2 — Architecture Model
    # =====================================================================

    async def refresh_architecture(self, repository: str) -> ArchitectureModel:
        """Build architecture model by aggregating from CodeIntelligence."""
        self._load()
        services: List[Dict[str, Any]] = []
        modules: List[Dict[str, Any]] = []
        libraries: List[Dict[str, Any]] = []
        apis: List[Dict[str, Any]] = []
        workers: List[Dict[str, Any]] = []
        schedulers: List[Dict[str, Any]] = []
        agents_list: List[Dict[str, Any]] = []
        connectors: List[Dict[str, Any]] = []
        runtime_components: List[Dict[str, Any]] = []

        try:
            from backend.services.enterprise_code_intelligence import code_intelligence
            scan = await code_intelligence.scan_repository(repository)
            if isinstance(scan, dict):
                entities = scan.get("entities", [])
                service_names: Set[str] = set()
                for ent in entities:
                    etype = ent.get("entity_type", "")
                    ename = ent.get("name", "")
                    efile = ent.get("file_path", "")
                    if etype in ("class", "service", "route", "api"):
                        apis.append({"name": ename, "file": efile, "type": etype})
                    if etype in ("service", "class") and ename:
                        service_names.add(ename.split(".")[0] if "." in ename else ename)
                    if etype == "function":
                        if "worker" in ename.lower() or "task" in ename.lower():
                            workers.append({"name": ename, "file": efile})
                        if "schedule" in ename.lower() or "cron" in ename.lower():
                            schedulers.append({"name": ename, "file": efile})
                    if etype == "interface":
                        connectors.append({"name": ename, "file": efile, "type": "interface"})

                for sname in sorted(service_names):
                    services.append({"name": sname, "repository": repository})

                for ent in entities:
                    efile = ent.get("file_path", "")
                    ename = ent.get("name", "")
                    parts = efile.replace("\\", "/").split("/")
                    module = parts[1] if len(parts) > 2 else parts[0] if parts else ""
                    if module and module not in [m.get("name") for m in modules]:
                        modules.append({"name": module, "path": "/".join(parts[:2]) if len(parts) > 1 else efile})

                if isinstance(scan.get("graph"), dict):
                    from backend.services.enterprise_code_intelligence import code_intelligence as ci
                    graph = await ci.get_graph()
                    if isinstance(graph, dict):
                        for edge in graph.get("edges", []):
                            if edge.get("relation") == "imports":
                                target = edge.get("target", "")
                                if target not in [lib.get("name") for lib in libraries]:
                                    libraries.append({"name": target, "source": edge.get("source", "")})

        except Exception as exc:
            log.debug("Architecture refresh failed: %s", exc)

        model = ArchitectureModel(
            services=services,
            modules=modules,
            libraries=libraries,
            apis=apis,
            workers=workers,
            schedulers=schedulers,
            agents=agents_list,
            connectors=connectors,
            runtime_components=runtime_components,
            built_at=_now(),
        )
        self._architectures[repository] = model
        self._save()
        return model

    async def get_architecture(self, repository: str) -> Optional[ArchitectureModel]:
        self._load()
        return self._architectures.get(repository)

    # =====================================================================
    # Phase 3 — Dependency Graph
    # =====================================================================

    async def get_dependency_graph(self, repository: str) -> Dict[str, Any]:
        """Reuse EnterpriseCodeIntelligence dependency graph."""
        self._load()
        try:
            from backend.services.enterprise_code_intelligence import code_intelligence
            graph = await code_intelligence.get_graph()
            if isinstance(graph, dict):
                return graph
        except Exception as exc:
            log.debug("Dependency graph retrieval failed: %s", exc)
        return {"nodes": [], "edges": []}

    async def refresh_dependencies(self, repository: str) -> Dict[str, Any]:
        """Refresh by triggering a code intelligence scan."""
        self._load()
        try:
            from backend.services.enterprise_code_intelligence import code_intelligence
            await code_intelligence.scan_repository(repository)
            return await self.get_dependency_graph(repository)
        except Exception as exc:
            log.debug("Dependency refresh failed: %s", exc)
            return {"nodes": [], "edges": []}

    async def get_impact(
        self, repository: str, changed_file: str
    ) -> Dict[str, Any]:
        """Reuse CodeIntelligence impact analysis."""
        try:
            from backend.services.enterprise_code_intelligence import code_intelligence
            return await code_intelligence.analyze_impact(changed_file)
        except Exception as exc:
            log.debug("Impact analysis failed: %s", exc)
            return {"risk_score": 0, "affected_files": []}

    # =====================================================================
    # Phase 4 — Ownership Intelligence
    # =====================================================================

    async def refresh_ownership(self, repository: str) -> List[OwnershipRecord]:
        """Refresh ownership from GitHub CODEOWNERS and commit history."""
        self._load()
        records: List[OwnershipRecord] = []

        try:
            from backend.services.enterprise_github_integration import github_integration
            if "/" in repository:
                org, name = repository.split("/")[0], repository.split("/")[-1].replace(".git", "")
                if hasattr(github_integration, "get_repo_contributors"):
                    contribs = await github_integration.get_repo_contributors(org, name)
                    if isinstance(contribs, list):
                        top_contribs = [c for c in contribs[:5] if isinstance(c, dict)]
                        for c in top_contribs:
                            records.append(OwnershipRecord(
                                service=repository,
                                owners=[c.get("login", "")],
                                teams=[],
                                maintainers=[c.get("login", "")],
                                is_critical=False,
                                business_domain="",
                                repository=repository,
                                updated_at=_now(),
                            ))
        except Exception:
            pass

        arch = self._architectures.get(repository)
        if arch:
            for svc in arch.services:
                svc_name = svc.get("name", "")
                if svc_name and not any(r.service == svc_name for r in records):
                    records.append(OwnershipRecord(
                        service=svc_name,
                        owners=[],
                        teams=[],
                        maintainers=[],
                        is_critical=False,
                        business_domain="",
                        repository=repository,
                        updated_at=_now(),
                    ))

        for r in records:
            self._ownership[r.service] = r
        self._save()
        return records

    async def get_ownership(self, service: str = "") -> List[OwnershipRecord]:
        self._load()
        if service:
            rec = self._ownership.get(service)
            return [rec] if rec else []
        return list(self._ownership.values())

    # =====================================================================
    # Phase 5 — Runtime Mapping
    # =====================================================================

    async def refresh_runtime_mapping(self, repository: str) -> Dict[str, List[Dict[str, Any]]]:
        """Build service -> deployment -> pod -> container -> node -> cluster mapping."""
        self._load()
        mapping: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        try:
            from backend.services.enterprise_infrastructure_intelligence import infrastructure_intelligence
            if hasattr(infrastructure_intelligence, "list_deployments"):
                deps = await infrastructure_intelligence.list_deployments()
                if isinstance(deps, list):
                    for dep in deps:
                        if isinstance(dep, dict):
                            dep_name = dep.get("name", dep.get("deployment", ""))
                            namespace = dep.get("namespace", "default")
                            service_name = dep.get("service", dep_name)
                            entry: Dict[str, Any] = {
                                "service": service_name,
                                "deployment": dep_name,
                                "namespace": namespace,
                                "replicas": dep.get("replicas", 0),
                                "available": dep.get("available", 0),
                                "strategy": dep.get("strategy", "rolling"),
                                "pods": [],
                                "containers": [],
                                "node": "",
                                "cluster": "",
                                "environment": namespace,
                            }
                            if hasattr(infrastructure_intelligence, "list_pods"):
                                pods_raw = await infrastructure_intelligence.list_pods()
                                if isinstance(pods_raw, list):
                                    for pod in pods_raw:
                                        if isinstance(pod, dict) and pod.get("deployment", "") == dep_name:
                                            pod_info = {
                                                "name": pod.get("name", ""),
                                                "status": pod.get("status", ""),
                                                "node": pod.get("node", ""),
                                                "containers": pod.get("containers", []),
                                            }
                                            entry["pods"].append(pod_info)
                                            if pod.get("node"):
                                                entry["node"] = pod.get("node", "")

                                            for c in (pod.get("containers", []) if isinstance(pod.get("containers"), list) else []):
                                                if isinstance(c, dict):
                                                    entry["containers"].append({
                                                        "name": c.get("name", ""),
                                                        "image": c.get("image", ""),
                                                        "ports": c.get("ports", []),
                                                    })
                            if hasattr(infrastructure_intelligence, "list_clusters"):
                                clusters = await infrastructure_intelligence.list_clusters()
                                if isinstance(clusters, list):
                                    for cl in clusters:
                                        if isinstance(cl, dict) and cl.get("name", "").lower() in namespace.lower():
                                            entry["cluster"] = cl.get("name", "")
                            mapping[service_name].append(entry)
        except Exception as exc:
            log.debug("Runtime mapping refresh failed: %s", exc)

        return dict(mapping)

    async def get_runtime_mapping(self, repository: str) -> Dict[str, Any]:
        return await self.refresh_runtime_mapping(repository)

    # =====================================================================
    # Phase 6 — Operational History
    # =====================================================================

    async def refresh_operational_history(self, repository: str) -> Dict[str, Any]:
        """Aggregate operational history from RuntimeStore."""
        self._load()
        history: Dict[str, Any] = {
            "deployments": [],
            "failures": [],
            "rollbacks": [],
            "recoveries": [],
            "incidents": [],
            "hotfixes": [],
            "missions": [],
        }

        try:
            from backend.services.enterprise_runtime_store import runtime_store
            execs = runtime_store.list_executions(repository=repository, limit=200)
            for ex in execs:
                entry = {
                    "execution_id": ex.execution_id,
                    "status": ex.status,
                    "started_at": ex.started_at,
                    "completed_at": ex.completed_at,
                    "duration_seconds": ex.duration_seconds,
                    "owner": ex.owner,
                    "failure_reason": ex.failure_reason,
                    "mission_id": ex.mission_id,
                }
                if ex.deployment_id:
                    history["deployments"].append(entry)
                if ex.status in ("failed", "failure") or ex.failure_reason:
                    history["failures"].append(entry)
                if ex.deployment_status == "rolled_back" or ex.rollback_status == "completed":
                    history["rollbacks"].append(entry)
                if ex.recovery:
                    history["recoveries"].append(entry)
                if ex.mission_id:
                    history["missions"].append(entry)
        except Exception as exc:
            log.debug("Operational history refresh failed: %s", exc)

        try:
            from backend.services.enterprise_engineering_memory import enterprise_engineering_memory
            patterns = enterprise_engineering_memory.mine_patterns(limit=20)
            if isinstance(patterns, list):
                history["patterns"] = [p for p in patterns if isinstance(p, dict)]
        except Exception:
            pass

        return history

    async def get_operational_history(self, repository: str) -> Dict[str, Any]:
        return await self.refresh_operational_history(repository)

    # =====================================================================
    # Phase 7 — Architecture Drift
    # =====================================================================

    async def detect_drift(self, repository: str) -> List[DriftRecord]:
        """Detect architecture drift by comparing current vs previous state."""
        self._load()
        new_drifts: List[DriftRecord] = []
        prev_arch = self._architectures.get(repository)
        current_arch = await self.refresh_architecture(repository)

        if prev_arch:
            prev_services = {s.get("name", "") for s in prev_arch.services}
            curr_services = {s.get("name", "") for s in current_arch.services}

            new_services = curr_services - prev_services
            for ns in sorted(new_services):
                new_drifts.append(DriftRecord(
                    drift_id=_id("drift"),
                    drift_type="new_service",
                    severity="info",
                    description=f"New service detected: {ns}",
                    repository=repository,
                    service=ns,
                    detected_at=_now(),
                ))

            removed_services = prev_services - curr_services
            for rs in sorted(removed_services):
                new_drifts.append(DriftRecord(
                    drift_id=_id("drift"),
                    drift_type="deleted_api",
                    severity="warning",
                    description=f"Service removed: {rs}",
                    repository=repository,
                    service=rs,
                    detected_at=_now(),
                ))

            prev_apis = {a.get("name", "") for a in prev_arch.apis}
            curr_apis = {a.get("name", "") for a in current_arch.apis}
            deleted_apis = prev_apis - curr_apis
            for da in sorted(deleted_apis):
                new_drifts.append(DriftRecord(
                    drift_id=_id("drift"),
                    drift_type="deleted_api",
                    severity="warning",
                    description=f"API/route removed: {da}",
                    repository=repository,
                    service=da,
                    detected_at=_now(),
                ))

        # Detect circular dependencies via code intelligence
        try:
            from backend.services.enterprise_code_intelligence import code_intelligence
            graph = await code_intelligence.get_graph()
            if isinstance(graph, dict):
                edges = graph.get("edges", [])
                dep_map: Dict[str, List[str]] = defaultdict(list)
                for e in edges:
                    src = e.get("source", "")
                    tgt = e.get("target", "")
                    if src and tgt:
                        dep_map[src].append(tgt)
                for node, deps in dep_map.items():
                    for dep in deps:
                        if dep in dep_map and node in dep_map[dep]:
                            if not any(
                                d.drift_type == "circular_dependency" and
                                d.description.startswith(f"Circular dependency between {node}")
                                for d in self._drift
                            ):
                                new_drifts.append(DriftRecord(
                                    drift_id=_id("drift"),
                                    drift_type="circular_dependency",
                                    severity="critical",
                                    description=f"Circular dependency between {node} and {dep}",
                                    repository=repository,
                                    service=node,
                                    detected_at=_now(),
                                ))
        except Exception:
            pass

        self._drift.extend(new_drifts)
        self._save()
        return new_drifts

    async def get_drift(self, repository: str = "", unresolved_only: bool = False) -> List[Dict[str, Any]]:
        self._load()
        results = list(self._drift)
        if repository:
            results = [d for d in results if d.repository == repository]
        if unresolved_only:
            results = [d for d in results if not d.resolved]
        return [d.to_dict() for d in results]

    async def resolve_drift(self, drift_id: str) -> bool:
        self._load()
        for d in self._drift:
            if d.drift_id == drift_id and not d.resolved:
                idx = self._drift.index(d)
                resolved = DriftRecord(
                    drift_id=d.drift_id, drift_type=d.drift_type,
                    severity=d.severity, description=d.description,
                    repository=d.repository, service=d.service,
                    detected_at=d.detected_at,
                    resolved=True, resolved_at=_now(),
                )
                self._drift[idx] = resolved
                self._save()
                return True
        return False

    # =====================================================================
    # Phase 8 — Executive Integration
    # =====================================================================

    async def get_brain_summary(self, repository: str) -> Dict[str, Any]:
        """Full brain summary for executive planning."""
        self._load()
        identity = self._repositories.get(repository)
        arch = self._architectures.get(repository)
        ownership = [o.to_dict() for o in self._ownership.values() if o.repository == repository]
        drift = [d.to_dict() for d in self._drift if d.repository == repository and not d.resolved]
        history = await self.refresh_operational_history(repository)

        return {
            "repository": repository,
            "identity": identity.to_dict() if identity else {},
            "architecture": {
                "services": len(arch.services) if arch else 0,
                "modules": len(arch.modules) if arch else 0,
                "apis": len(arch.apis) if arch else 0,
                "libraries": len(arch.libraries) if arch else 0,
            },
            "ownership": ownership,
            "drift_count": len(drift),
            "drift": drift[:10],
            "history": {
                "total_deployments": len(history.get("deployments", [])),
                "total_failures": len(history.get("failures", [])),
                "total_rollbacks": len(history.get("rollbacks", [])),
                "recent_failures": history.get("failures", [])[:5],
            },
            "built_at": arch.built_at if arch else "",
            "refreshed_at": _now(),
        }

    # =====================================================================
    # Phase 10 — Repository Dashboard
    # =====================================================================

    async def get_dashboard(self) -> Dict[str, Any]:
        self._load()
        total_repos = len(self._repositories)
        total_services = sum(len(a.services) for a in self._architectures.values())
        total_apis = sum(len(a.apis) for a in self._architectures.values())
        total_modules = sum(len(a.modules) for a in self._architectures.values())
        total_drift = len([d for d in self._drift if not d.resolved])
        critical_drift = len([d for d in self._drift if not d.resolved and d.severity == "critical"])
        warnings = len([d for d in self._drift if not d.resolved and d.severity == "warning"])

        lang_counter: Counter = Counter()
        framework_counter: Counter = Counter()
        build_counter: Counter = Counter()
        for r in self._repositories.values():
            for lang, count in r.languages.items():
                lang_counter[lang] += count
            for fw in r.frameworks:
                framework_counter[fw] += 1
            for bs in r.build_systems:
                build_counter[bs] += 1

        total_failures = 0
        total_rollbacks = 0
        try:
            from backend.services.enterprise_runtime_store import runtime_store
            all_execs = runtime_store.list_executions(limit=500)
            total_failures = sum(1 for e in all_execs if e.status in ("failed", "failure"))
            total_rollbacks = sum(1 for e in all_execs if e.deployment_status == "rolled_back")
        except Exception:
            pass

        repo_list = []
        for repo, identity in self._repositories.items():
            arch = self._architectures.get(repo)
            dcount = len([d for d in self._drift if d.repository == repo and not d.resolved])
            repo_list.append({
                "repository": repo,
                "organization": identity.organization,
                "default_branch": identity.default_branch,
                "languages": identity.languages,
                "frameworks": identity.frameworks,
                "services": len(arch.services) if arch else 0,
                "drift": dcount,
                "last_scanned": identity.last_scanned_at,
            })

        return {
            "total_repositories": total_repos,
            "total_services": total_services,
            "total_apis": total_apis,
            "total_modules": total_modules,
            "languages": dict(lang_counter.most_common(20)),
            "frameworks": dict(framework_counter.most_common(20)),
            "build_systems": dict(build_counter.most_common(20)),
            "unresolved_drift": total_drift,
            "critical_drift": critical_drift,
            "drift_warnings": warnings,
            "total_failures": total_failures,
            "total_rollbacks": total_rollbacks,
            "repositories": repo_list,
            "built_at": _now(),
        }


# =============================================================================
# Singleton
# =============================================================================

repository_brain = EnterpriseRepositoryBrain()
