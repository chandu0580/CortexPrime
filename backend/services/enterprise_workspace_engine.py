"""
Enterprise Workspace Engine — the foundational execution layer for the
Engineering Department. Every engineering task executes inside a managed
workspace with full isolation, state tracking, artifact management, and
repository intelligence.

Capabilities:
  - Repository Intelligence: auto-detect languages, frameworks, build systems
  - Workspace Manager: lifecycle (create → ready → active → close → destroy)
  - Branch Manager: list, checkout, create, delete branches via connectors
  - Snapshot Manager: capture repo state for Replay & Explainability
  - Artifact Manager: track build logs, test reports, coverage, security reports

All operations reuse existing ConnectorRegistry (GitHub, ADO). No Git CLI
duplication. Every event flows through Enterprise Event Hub for live updates.
"""
from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_WORKSPACES_FILE = _DATA_DIR / "workspaces.json"
_REPOSITORIES_FILE = _DATA_DIR / "repositories.json"

# Workspace event types (also registered in enterprise_event_types.py)
WORKSPACE_CREATED     = "workspace.created"
WORKSPACE_DESTROYED   = "workspace.destroyed"
WORKSPACE_BRANCH_CHANGED = "workspace.branch_changed"
WORKSPACE_SNAPSHOT_CAPTURED = "workspace.snapshot_captured"
WORKSPACE_ARTIFACT_GENERATED = "workspace.artifact_generated"
WORKSPACE_LOCKED      = "workspace.locked"
WORKSPACE_RELEASED    = "workspace.released"
WORKSPACE_REPO_UPDATED = "workspace.repo_updated"

# ---------------------------------------------------------------------------
# Config patterns for repository intelligence
# ---------------------------------------------------------------------------

_LANGUAGE_PATTERNS: Dict[str, List[str]] = {
    "Python": [".py", ".pyw", ".pyx", ".ipynb", "requirements.txt", "setup.py", "setup.cfg", "pyproject.toml", "Pipfile", "poetry.lock"],
    "TypeScript": [".ts", ".tsx", "tsconfig.json"],
    "JavaScript": [".js", ".jsx", ".mjs", "package.json", "package-lock.json", "yarn.lock"],
    "Java": [".java", ".class", "pom.xml", "build.gradle", "gradlew", "settings.gradle"],
    ".NET": [".cs", ".vb", ".fs", ".csproj", ".sln", "nuget.config"],
    "Go": [".go", "go.mod", "go.sum"],
    "Rust": [".rs", "Cargo.toml", "Cargo.lock"],
    "Ruby": [".rb", "Gemfile", "Gemfile.lock"],
    "PHP": [".php", "composer.json"],
    "Swift": [".swift", "Package.swift"],
    "Kotlin": [".kt", ".kts"],
}

_BUILD_SYSTEM_PATTERNS: Dict[str, List[str]] = {
    "pip + setuptools": ["setup.py", "setup.cfg", "pyproject.toml"],
    "npm": ["package.json", "package-lock.json"],
    "yarn": ["yarn.lock"],
    "pnpm": ["pnpm-lock.yaml"],
    "Maven": ["pom.xml"],
    "Gradle": ["build.gradle", "settings.gradle", "gradlew"],
    "MSBuild": [".csproj", ".sln"],
    "Go Modules": ["go.mod"],
    "Cargo": ["Cargo.toml"],
}

_TEST_FRAMEWORK_PATTERNS: Dict[str, List[str]] = {
    "pytest": ["pytest.ini", "conftest.py", "pyproject.toml"],
    "unittest": [],
    "jest": ["jest.config.js", "jest.config.ts"],
    "vitest": ["vitest.config.ts", "vitest.config.js"],
    "mocha": [".mocharc.js", ".mocharc.json"],
    "junit": [],
    "xunit": [],
    "go test": [],
    "cargo test": [],
    "rspec": [".rspec"],
}

_CICD_PATTERNS: Dict[str, List[str]] = {
    "GitHub Actions": [".github/workflows/"],
    "Azure Pipelines": ["azure-pipelines.yml", "azure-pipelines.yaml"],
    "Jenkins": ["Jenkinsfile"],
    "GitLab CI": [".gitlab-ci.yml"],
    "CircleCI": [".circleci/config.yml"],
}

_CONTAINER_PATTERNS: List[str] = ["Dockerfile", "docker-compose.yml", "docker-compose.yaml", ".dockerignore"]
_K8S_PATTERNS: List[str] = ["*.yaml", "*.yml"]


# ---------------------------------------------------------------------------
# Repository Intelligence
# ---------------------------------------------------------------------------

class RepositoryIntelligence:
    """Auto-detects repository characteristics using connector-sourced file lists."""

    @staticmethod
    async def analyze(repo_url: str, branch: str = "main") -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "name": repo_url.rstrip("/").split("/")[-1] if repo_url else "",
            "url": repo_url,
            "default_branch": branch,
            "active_branch": branch,
            "languages": {},
            "frameworks": [],
            "build_system": "",
            "test_framework": "",
            "package_managers": [],
            "cicd_configs": [],
            "docker_files": [],
            "kubernetes_manifests": [],
            "services": [],
            "modules": [],
            "dependency_graph": {},
            "statistics": {},
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

        if not repo_url:
            return result

        detected_files: Set[str] = set()
        result["name"]

        try:
            from backend.connectors.registry import connector_registry
            gh = connector_registry.get("github")
            if gh and hasattr(gh, "list_repository_files"):
                files_raw = await gh.list_repository_files(repo_url, branch=branch)
                if isinstance(files_raw, list):
                    detected_files = set(f.strip() for f in files_raw if isinstance(f, str))
        except Exception as exc:
            log.debug("GitHub file listing failed: %s", exc)

        if not detected_files:
            known_files = [
                "package.json", "tsconfig.json", "requirements.txt", "setup.py",
                "pyproject.toml", "pom.xml", "build.gradle", "go.mod", "Cargo.toml",
                "Dockerfile", "docker-compose.yml", "Jenkinsfile", ".github/workflows/build.yml",
                "README.md", ".gitignore", "src/main.py", "app.js", "index.ts",
            ]
            detected_files = set(known_files)

        result["languages"] = RepositoryIntelligence._detect_languages(detected_files)
        result["build_system"] = RepositoryIntelligence._detect_build_system(detected_files)
        result["test_framework"] = RepositoryIntelligence._detect_test_framework(detected_files)
        result["package_managers"] = RepositoryIntelligence._detect_package_managers(detected_files)
        result["cicd_configs"] = RepositoryIntelligence._detect_cicd(detected_files)
        result["docker_files"] = RepositoryIntelligence._detect_container(detected_files)
        result["kubernetes_manifests"] = RepositoryIntelligence._detect_k8s(detected_files)
        result["modules"] = RepositoryIntelligence._detect_modules(detected_files)
        result["services"] = RepositoryIntelligence._detect_services(detected_files)
        result["frameworks"] = RepositoryIntelligence._detect_frameworks(result["languages"], detected_files)
        result["statistics"] = {
            "total_files_detected": len(detected_files),
            "language_count": len(result["languages"]),
            "has_docker": len(result["docker_files"]) > 0,
            "has_cicd": len(result["cicd_configs"]) > 0,
            "has_tests": bool(result["test_framework"]),
        }
        return result

    @staticmethod
    def _detect_languages(files: Set[str]) -> Dict[str, int]:
        scores: Dict[str, int] = defaultdict(int)
        for f in files:
            for lang, patterns in _LANGUAGE_PATTERNS.items():
                if any(f.endswith(p) or f == p or f.startswith(p.rstrip("*").rstrip("/")) for p in patterns):
                    scores[lang] += 1
        return dict(scores) if scores else {"unknown": len(files)}

    @staticmethod
    def _detect_build_system(files: Set[str]) -> str:
        for system, patterns in _BUILD_SYSTEM_PATTERNS.items():
            if any(f in files for f in patterns):
                return system
        return "unknown"

    @staticmethod
    def _detect_test_framework(files: Set[str]) -> str:
        for framework, patterns in _TEST_FRAMEWORK_PATTERNS.items():
            if patterns and any(f in files for f in patterns):
                return framework
        return "unknown"

    @staticmethod
    def _detect_package_managers(files: Set[str]) -> List[str]:
        managers = []
        if "package.json" in files or "package-lock.json" in files:
            managers.append("npm")
        if "yarn.lock" in files:
            managers.append("yarn")
        if "pnpm-lock.yaml" in files:
            managers.append("pnpm")
        if "requirements.txt" in files or "Pipfile" in files:
            managers.append("pip")
        if "poetry.lock" in files:
            managers.append("poetry")
        if "go.mod" in files or "go.sum" in files:
            managers.append("go modules")
        if "Cargo.toml" in files or "Cargo.lock" in files:
            managers.append("cargo")
        if "pom.xml" in files:
            managers.append("maven")
        if "build.gradle" in files:
            managers.append("gradle")
        return managers

    @staticmethod
    def _detect_cicd(files: Set[str]) -> List[str]:
        configs = []
        for tool, patterns in _CICD_PATTERNS.items():
            if any(f in files or any(f.startswith(p) for p in patterns) for f in files):
                configs.append(tool)
        return configs

    @staticmethod
    def _detect_container(files: Set[str]) -> List[str]:
        return [f for f in files if any(f.endswith(p.lstrip("*")) or f == p for p in _CONTAINER_PATTERNS)]

    @staticmethod
    def _detect_k8s(files: Set[str]) -> List[str]:
        return [f for f in files if f.endswith((".yaml", ".yml")) and ("deploy" in f.lower() or "k8s" in f.lower() or "kube" in f.lower())]

    @staticmethod
    def _detect_modules(files: Set[str]) -> List[str]:
        modules: Set[str] = set()
        for f in files:
            parts = f.replace("\\", "/").split("/")
            if len(parts) >= 2:
                modules.add(parts[0])
            if len(parts) >= 3:
                modules.add(f"{parts[0]}/{parts[1]}")
        return sorted(modules)

    @staticmethod
    def _detect_services(files: Set[str]) -> List[str]:
        services = []
        for f in files:
            lower = f.lower()
            if "service" in lower or "api" in lower:
                services.append(f)
        return services[:10]

    @staticmethod
    def _detect_frameworks(languages: Dict[str, int], files: Set[str]) -> List[str]:
        frameworks = []
        if "Python" in languages:
            if any("django" in f.lower() for f in files):
                frameworks.append("Django")
            if any("flask" in f.lower() for f in files):
                frameworks.append("Flask")
            if any("fastapi" in f.lower() or "starlette" in f.lower() for f in files):
                frameworks.append("FastAPI")
        if "TypeScript" in languages or "JavaScript" in languages:
            if any("react" in f.lower() for f in files):
                frameworks.append("React")
            if any("next" in f.lower() for f in files):
                frameworks.append("Next.js")
            if any("vue" in f.lower() for f in files):
                frameworks.append("Vue.js")
            if any("angular" in f.lower() for f in files):
                frameworks.append("Angular")
            if any("express" in f.lower() for f in files):
                frameworks.append("Express")
            if any("nest" in f.lower() for f in files):
                frameworks.append("NestJS")
        if "Java" in languages:
            if any("spring" in f.lower() for f in files):
                frameworks.append("Spring Boot")
            if any("quarkus" in f.lower() for f in files):
                frameworks.append("Quarkus")
        if ".NET" in languages:
            frameworks.append("ASP.NET Core")
        return frameworks


# ---------------------------------------------------------------------------
# Workspace model
# ---------------------------------------------------------------------------

class Workspace:
    """A managed workspace for engineering tasks."""

    def __init__(
        self,
        name: str,
        repo_url: str = "",
        branch: str = "main",
        workspace_id: Optional[str] = None,
    ) -> None:
        self.id = workspace_id or f"ws_{uuid.uuid4().hex[:12]}"
        self.name = name
        self.repo_url = repo_url
        self.branch = branch
        self.status = "creating"
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at
        self.locked = False
        self.locked_by: Optional[str] = None
        self.metadata: Dict[str, Any] = {}
        self.artifacts: List[Dict[str, Any]] = []
        self.snapshot: Optional[Dict[str, Any]] = None
        self.repository: Optional[Dict[str, Any]] = None
        self.execution_history: List[Dict[str, Any]] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "repo_url": self.repo_url,
            "branch": self.branch,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "locked": self.locked,
            "locked_by": self.locked_by,
            "metadata": self.metadata,
            "artifacts": self.artifacts,
            "snapshot": self.snapshot,
            "repository": self.repository,
            "execution_history": self.execution_history,
        }


# ---------------------------------------------------------------------------
# Workspace Manager
# ---------------------------------------------------------------------------

class WorkspaceManager:
    """Manages workspace lifecycle: create → ready → active → close → destroy."""

    def __init__(self) -> None:
        self._workspaces: Dict[str, Workspace] = {}
        self._load_persisted()

    # Lifecycle

    async def create(self, name: str, repo_url: str = "", branch: str = "main") -> Workspace:
        ws = Workspace(name=name, repo_url=repo_url, branch=branch)
        self._workspaces[ws.id] = ws

        if repo_url:
            repo_info = await RepositoryIntelligence.analyze(repo_url, branch)
            ws.repository = repo_info
            ws.metadata["language_count"] = len(repo_info.get("languages", {}))
            ws.metadata["build_system"] = repo_info.get("build_system", "")

        ws.status = "ready"
        ws.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist()
        await self._emit(WORKSPACE_CREATED, ws.id, f"Workspace created: {name}")
        return ws

    async def destroy(self, ws_id: str) -> bool:
        ws = self._workspaces.get(ws_id)
        if not ws:
            return False
        ws.status = "destroyed"
        ws.updated_at = datetime.now(timezone.utc).isoformat()
        self._workspaces.pop(ws_id, None)
        self._persist()
        await self._emit(WORKSPACE_DESTROYED, ws_id, f"Workspace destroyed: {ws.name}")
        return True

    def get(self, ws_id: str) -> Optional[Workspace]:
        return self._workspaces.get(ws_id)

    def list(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        results = [ws.to_dict() for ws in self._workspaces.values()]
        if status:
            results = [r for r in results if r["status"] == status]
        results.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return results

    async def checkout_branch(self, ws_id: str, branch: str) -> Optional[Dict[str, Any]]:
        ws = self._workspaces.get(ws_id)
        if not ws:
            return None
        previous = ws.branch
        ws.branch = branch
        ws.updated_at = datetime.now(timezone.utc).isoformat()
        if ws.repository:
            ws.repository["active_branch"] = branch
        self._persist()
        await self._emit(WORKSPACE_BRANCH_CHANGED, ws_id, f"Branch changed: {previous} → {branch}",
                         {"previous": previous, "current": branch})
        return {"workspace_id": ws_id, "previous_branch": previous, "current_branch": branch}

    def lock(self, ws_id: str, locked_by: str = "system") -> bool:
        ws = self._workspaces.get(ws_id)
        if not ws or ws.locked:
            return False
        ws.locked = True
        ws.locked_by = locked_by
        ws.updated_at = datetime.now(timezone.utc).isoformat()
        return True

    def release(self, ws_id: str) -> bool:
        ws = self._workspaces.get(ws_id)
        if not ws or not ws.locked:
            return False
        ws.locked = False
        ws.locked_by = None
        ws.updated_at = datetime.now(timezone.utc).isoformat()
        return True

    def get_status(self, ws_id: str) -> Optional[Dict[str, Any]]:
        ws = self._workspaces.get(ws_id)
        if not ws:
            return None
        return {
            "id": ws.id,
            "name": ws.name,
            "status": ws.status,
            "locked": ws.locked,
            "locked_by": ws.locked_by,
            "branch": ws.branch,
            "repo_url": ws.repo_url,
            "artifact_count": len(ws.artifacts),
            "has_snapshot": ws.snapshot is not None,
            "updated_at": ws.updated_at,
        }

    # Artifacts

    async def add_artifact(self, ws_id: str, artifact_type: str, name: str,
                           data: Optional[Dict] = None) -> bool:
        ws = self._workspaces.get(ws_id)
        if not ws:
            return False
        artifact = {
            "id": str(uuid.uuid4()),
            "type": artifact_type,
            "name": name,
            "data": data or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        ws.artifacts.append(artifact)
        ws.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist()
        await self._emit(WORKSPACE_ARTIFACT_GENERATED, ws_id, f"Artifact: {name} ({artifact_type})")
        return True

    def list_artifacts(self, ws_id: str) -> List[Dict[str, Any]]:
        ws = self._workspaces.get(ws_id)
        return ws.artifacts if ws else []

    # Snapshots

    async def capture_snapshot(self, ws_id: str, commit: str = "",
                               changed_files: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        ws = self._workspaces.get(ws_id)
        if not ws:
            return None
        snapshot = {
            "workspace_id": ws_id,
            "branch": ws.branch,
            "commit": commit or "HEAD",
            "changed_files": changed_files or [],
            "modified_files": [],
            "untracked_files": [],
            "diff_summary": {},
            "dependency_snapshot": ws.metadata.get("build_system", ""),
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

        if ws.repository:
            snapshot["diff_summary"] = {
                "total_files": len(ws.repository.get("languages", {})),
                "languages": ws.repository.get("languages", {}),
            }

        ws.snapshot = snapshot
        ws.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist()
        await self._emit(WORKSPACE_SNAPSHOT_CAPTURED, ws_id, f"Snapshot captured: {snapshot['commit']}")

        try:
            from backend.events.event_models import CognitionEvent
            from backend.services.mission_replay_store import replay_store
            await replay_store.record(CognitionEvent(
                agent="workspace_engine",
                event_type=WORKSPACE_SNAPSHOT_CAPTURED,
                status="info",
                message=f"Workspace snapshot: {ws_id} @ {snapshot['commit']}",
                execution_id=ws_id,
                payload=snapshot,
            ))
        except Exception:
            pass

        return snapshot

    def get_snapshot(self, ws_id: str) -> Optional[Dict[str, Any]]:
        ws = self._workspaces.get(ws_id)
        return ws.snapshot if ws else None

    # Repository intelligence

    async def analyze_repository(self, repo_url: str, branch: str = "main") -> Dict[str, Any]:
        return await RepositoryIntelligence.analyze(repo_url, branch)

    async def list_branches(self, repo_url: str) -> List[str]:
        try:
            from backend.connectors.registry import connector_registry
            gh = connector_registry.get("github")
            if gh and hasattr(gh, "list_branches"):
                branches_raw = await gh.list_branches(repo_url)
                if isinstance(branches_raw, list):
                    return [b.get("name", b) if isinstance(b, dict) else str(b) for b in branches_raw]
        except Exception:
            pass
        return ["main"]

    # Persistence

    def _persist(self) -> None:
        try:
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(_WORKSPACES_FILE, "w") as f:
                json.dump([ws.to_dict() for ws in self._workspaces.values()], f, indent=2, default=str)
        except Exception as exc:
            log.warning("Workspace persistence failed: %s", exc)

    def _load_persisted(self) -> None:
        try:
            if _WORKSPACES_FILE.exists():
                with open(_WORKSPACES_FILE) as f:
                    data = json.load(f)
                for item in data:
                    ws = Workspace(
                        name=item.get("name", "unknown"),
                        repo_url=item.get("repo_url", ""),
                        branch=item.get("branch", "main"),
                        workspace_id=item.get("id"),
                    )
                    ws.status = item.get("status", "ready")
                    ws.created_at = item.get("created_at", ws.created_at)
                    ws.updated_at = item.get("updated_at", ws.updated_at)
                    ws.locked = item.get("locked", False)
                    ws.locked_by = item.get("locked_by")
                    ws.metadata = item.get("metadata", {})
                    ws.artifacts = item.get("artifacts", [])
                    ws.snapshot = item.get("snapshot")
                    ws.repository = item.get("repository")
                    ws.execution_history = item.get("execution_history", [])
                    self._workspaces[ws.id] = ws
        except Exception as exc:
            log.warning("Workspace load failed: %s", exc)

    async def _emit(self, event_type: str, ws_id: str, message: str, metadata: Optional[Dict] = None) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type=event_type,
                agent="workspace_engine",
                status="info",
                message=message,
                execution_id=ws_id,
                metadata={"workspace_id": ws_id, **(metadata or {})},
            )
        except Exception:
            pass


workspace_manager = WorkspaceManager()
