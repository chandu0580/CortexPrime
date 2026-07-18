"""
Enterprise Code Intelligence Engine — understands repository structure,
dependencies, APIs, services, modules, functions, classes, database models,
frontend components, configuration, and relationships.

Parts:
  1. Repository Scanner — languages, packages, modules, builds
  2. Code Parser — functions, classes, routes, services, models, components
  3. Dependency Graph — call, module, service, API, DB, component graphs
  4. Code Knowledge Graph — extend with code entities and relationships
  5. Impact Analysis — affected files, APIs, tests, services, risk score
"""
from __future__ import annotations

import ast
import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from backend.events.enterprise_event_types import EnterpriseEventTypes as EET

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_REPOS_FILE = _DATA_DIR / "code_intelligence_repos.json"
_GRAPH_FILE = _DATA_DIR / "code_intelligence_graph.json"

# ── Language file extensions ─────────────────────────────────────────────────

LANGUAGE_EXTENSIONS: Dict[str, List[str]] = {
    "python":      [".py", ".pyw", ".pyx"],
    "typescript":  [".ts", ".tsx"],
    "javascript":  [".js", ".jsx", ".mjs"],
    "java":        [".java", ".kt", ".groovy", ".scala"],
    "dotnet":      [".cs", ".vb", ".fs", ".csproj", ".sln"],
    "go":          [".go"],
    "rust":        [".rs", ".rlib"],
    "ruby":        [".rb", ".erb"],
    "php":         [".php", ".phtml"],
    "swift":       [".swift"],
    "kotlin":      [".kt", ".kts"],
    "shell":       [".sh", ".bash", ".zsh", ".ps1"],
    "yaml":        [".yml", ".yaml"],
    "markdown":    [".md", ".mdx"],
    "docker":      ["Dockerfile"],
    "config":      [".json", ".toml", ".ini", ".cfg", ".conf"],
}

EXTENSION_TO_LANGUAGE: Dict[str, str] = {}
for lang, exts in LANGUAGE_EXTENSIONS.items():
    for ext in exts:
        EXTENSION_TO_LANGUAGE[ext] = lang


# =============================================================================
# Part 1 — Repository Scanner
# =============================================================================

class RepositoryScanner:
    """Scans a repository directory and discovers structure."""

    IGNORE_DIRS = {
        ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
        ".tox", ".eggs", "dist", "build", ".next", ".nuxt",
        ".gradle", "target", "bin", "obj", ".idea", ".vscode",
        ".DS_Store", "coverage", ".pytest_cache", ".mypy_cache",
    }

    IGNORE_FILES = {
        ".gitignore", ".gitkeep", ".DS_Store", "*.pyc", "*.pyo",
        "*.whl", "*.egg", "*.so", "*.o", "*.class",
    }

    CONFIG_FILES = {
        "package.json", "tsconfig.json", "requirements.txt", "setup.py",
        "setup.cfg", "pyproject.toml", "pom.xml", "build.gradle",
        "Cargo.toml", "go.mod", "go.sum", "Gemfile", "composer.json",
        "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
        "Makefile", "Justfile", ".env", ".env.example",
        ".github/workflows", ".gitlab-ci.yml", "Jenkinsfile",
        ".pre-commit-config.yaml", "eslintrc.js", ".prettierrc",
        "webpack.config.js", "vite.config.ts", "next.config.js",
    }

    @staticmethod
    def scan(directory: str) -> Dict[str, Any]:
        path = Path(directory)
        if not path.exists():
            return {"error": f"Directory not found: {directory}", "files": [], "languages": {}}

        files: List[Dict[str, Any]] = []
        languages: Dict[str, int] = defaultdict(int)
        packages: Set[str] = set()
        modules: Set[str] = set()
        configs: List[str] = []
        build_systems: Set[str] = set()
        total_size = 0

        for root, dirs, filenames in os.walk(str(path)):
            rel_root = Path(root).relative_to(path)
            dirs[:] = [d for d in dirs if d not in RepositoryScanner.IGNORE_DIRS]

            for fname in filenames:
                fpath = Path(root) / fname
                rel_path = str(rel_root / fname) if str(rel_root) != "." else fname

                try:
                    size = fpath.stat().st_size
                except Exception:
                    size = 0
                total_size += size

                ext = fpath.suffix.lower()
                lang = EXTENSION_TO_LANGUAGE.get(ext, "unknown")
                if fname == "Dockerfile":
                    lang = "docker"

                if lang != "unknown":
                    languages[lang] += 1

                entry = {
                    "path": rel_path,
                    "name": fname,
                    "extension": ext,
                    "language": lang,
                    "size_bytes": size,
                    "directory": str(rel_root) if str(rel_root) != "." else "",
                }
                files.append(entry)

                if fname in RepositoryScanner.CONFIG_FILES:
                    configs.append(rel_path)
                    bs = RepositoryScanner._detect_build_system(fname, rel_path)
                    if bs:
                        build_systems.add(bs)

                # Detect packages/modules from directories
                parts = rel_path.replace("\\", "/").split("/")
                if len(parts) >= 2:
                    pkg = parts[0]
                    if pkg not in ("__pycache__", ".git", "node_modules"):
                        packages.add(pkg)
                if len(parts) >= 2:
                    mod = parts[-2] if len(parts) >= 2 else ""
                    if mod and mod not in RepositoryScanner.IGNORE_DIRS:
                        modules.add(mod)

        return {
            "directory": directory,
            "total_files": len(files),
            "total_size_bytes": total_size,
            "languages": dict(languages),
            "packages": sorted(packages),
            "modules": sorted(modules),
            "configs": configs,
            "build_systems": sorted(build_systems),
            "files": files,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _detect_build_system(fname: str, rel_path: str) -> str:
        mapping = {
            "package.json": "npm", "tsconfig.json": "typescript",
            "requirements.txt": "pip", "setup.py": "setuptools",
            "setup.cfg": "setuptools", "pyproject.toml": "python",
            "pom.xml": "maven", "build.gradle": "gradle",
            "Cargo.toml": "cargo", "go.mod": "go-modules",
            "Gemfile": "bundler", "composer.json": "composer",
            "Dockerfile": "docker", "Makefile": "make",
        }
        return mapping.get(fname, "")


# =============================================================================
# Part 2 — Code Parser
# =============================================================================

class CodeContext:
    """Represents a parsed code element."""

    def __init__(self, entity_type: str, name: str, file_path: str,
                 line_start: int = 0, line_end: int = 0,
                 docstring: str = "", parent: str = "",
                 metadata: Optional[Dict[str, Any]] = None):
        self.id = f"{entity_type}:{file_path}:{name}:{line_start}"
        self.entity_type = entity_type
        self.name = name
        self.file_path = file_path
        self.line_start = line_start
        self.line_end = line_end
        self.docstring = docstring
        self.parent = parent
        self.metadata = metadata or {}
        self.relationships: List[Dict[str, str]] = []

    def add_relation(self, rel_type: str, target_id: str, target_name: str = "") -> None:
        self.relationships.append({
            "type": rel_type, "target_id": target_id, "target_name": target_name,
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "name": self.name,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "docstring": self.docstring[:200] if self.docstring else "",
            "parent": self.parent,
            "metadata": self.metadata,
            "relationships": self.relationships,
        }


class CodeParser:
    """Parses code files and extracts structural elements."""

    # ── Python ──────────────────────────────────────────────────────────────

    @staticmethod
    def parse_python(file_path: str, content: str) -> List[CodeContext]:
        elements: List[CodeContext] = []
        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError:
            return elements

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                ctx = CodeContext("function", node.name, file_path,
                                  node.lineno or 0, node.end_lineno or 0,
                                  ast.get_docstring(node) or "")
                CodeParser._extract_python_decorators(node, ctx)
                CodeParser._extract_calls(node, ctx)
                elements.append(ctx)

            elif isinstance(node, ast.AsyncFunctionDef):
                ctx = CodeContext("async_function", node.name, file_path,
                                  node.lineno or 0, node.end_lineno or 0,
                                  ast.get_docstring(node) or "")
                CodeParser._extract_python_decorators(node, ctx)
                elements.append(ctx)

            elif isinstance(node, ast.ClassDef):
                bases = [b.id if isinstance(b, ast.Name) else "" for b in node.bases]
                ctx = CodeContext("class", node.name, file_path,
                                  node.lineno or 0, node.end_lineno or 0,
                                  ast.get_docstring(node) or "",
                                  metadata={"bases": [b for b in bases if b]})
                CodeParser._extract_python_decorators(node, ctx)
                elements.append(ctx)

        # Detect routes, services, models
        CodeParser._detect_python_patterns(file_path, content, elements)
        return elements

    @staticmethod
    def _extract_python_decorators(node: ast.AST, ctx: CodeContext) -> None:
        decorators: List[str] = []
        for dec in getattr(node, "decorator_list", []):
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                decorators.append(f"{dec.func.value.id}.{dec.func.attr}" if isinstance(dec.func.value, ast.Name) else "")
            elif isinstance(dec, ast.Attribute):
                decorators.append(f"{dec.value.id}.{dec.attr}" if isinstance(dec.value, ast.Name) else "")
            elif isinstance(dec, ast.Name):
                decorators.append(dec.id)
        ctx.metadata["decorators"] = [d for d in decorators if d]

    @staticmethod
    def _extract_calls(node: ast.AST, ctx: CodeContext) -> None:
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                ctx.add_relation("calls", f"function:unknown:{child.func.id}:0", child.func.id)
            elif isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                ctx.add_relation("calls_method", f"method:{child.func.attr}:0", child.func.attr)

    @staticmethod
    def _detect_python_patterns(file_path: str, content: str, elements: List[CodeContext]) -> None:
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # FastAPI routes
            route_match = re.match(r'@(?:router|app)\.(?:get|post|put|delete|patch)\s*\(\s*["\'](.+?)["\']', stripped)
            if route_match:
                ctx = CodeContext("route", route_match.group(1), file_path, i, i,
                                  metadata={"method": stripped.split(".")[1].split("(")[0]})
                elements.append(ctx)
            # SQLAlchemy models
            if re.search(r"class\s+\w+\(.*Base\)", stripped):
                ctx = CodeContext("model", stripped.split("class ")[1].split("(")[0], file_path, i, i)
                elements.append(ctx)
            # Service classes
            if re.search(r"class\s+\w+Service", stripped):
                ctx = CodeContext("service", stripped.split("class ")[1].split("(")[0], file_path, i, i)
                elements.append(ctx)

    # ── TypeScript / JavaScript ──────────────────────────────────────────────

    @staticmethod
    def parse_typescript(file_path: str, content: str) -> List[CodeContext]:
        elements: List[CodeContext] = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # React hooks — check before functions so useHook() is hook not function
            hook_match = re.match(r"(?:export\s+)?(?:const\s+|function\s+)?(use\w+)\s*[(:=\[]", stripped)
            if hook_match:
                elements.append(CodeContext("hook", hook_match.group(1), file_path, i, i))
                continue

            # Functions
            fn_match = re.match(
                r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(", stripped
            )
            if fn_match:
                elements.append(CodeContext("function", fn_match.group(1), file_path, i, i))
                continue

            # Arrow functions (const/let)
            arrow_match = re.match(
                r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(.*\)\s*=>", stripped
            )
            if arrow_match and "React." not in stripped:
                elements.append(CodeContext("function", arrow_match.group(1), file_path, i, i))

            # Classes
            class_match = re.match(
                r"(?:export\s+)?(?:abstract\s+)?class\s+(\w+)", stripped
            )
            if class_match:
                extends = ""
                ext_match = re.search(r"extends\s+(\w+)", stripped)
                if ext_match:
                    extends = ext_match.group(1)
                elements.append(CodeContext("class", class_match.group(1), file_path, i, i,
                                            metadata={"extends": extends}))
                continue

            # Interfaces
            if_match = re.match(r"(?:export\s+)?interface\s+(\w+)", stripped)
            if if_match:
                elements.append(CodeContext("interface", if_match.group(1), file_path, i, i))
                continue

            # Enums
            enum_match = re.match(r"(?:export\s+)?enum\s+(\w+)", stripped)
            if enum_match:
                elements.append(CodeContext("enum", enum_match.group(1), file_path, i, i))
                continue

            # React components (PascalCase functions returning JSX)
            if "=>" in stripped and re.match(r"(?:export\s+)?(?:const|function)\s+([A-Z]\w+)", stripped):
                elements.append(CodeContext("react_component", re.match(
                    r"(?:export\s+)?(?:const|function)\s+([A-Z]\w+)", stripped).group(1), file_path, i, i))
                continue

            # Express/Fastify routes
            route_match = re.match(
                r'(?:router|app)\.(?:get|post|put|delete|patch)\s*\(\s*["\'](.+?)["\']', stripped
            )
            if route_match:
                elements.append(CodeContext("route", route_match.group(1), file_path, i, i,
                                            metadata={"method": stripped.split(".")[1].split("(")[0]}))
                continue

            # NestJS controllers/services
            if re.search(r"@(?:Controller|Injectable|Service|Entity|Module)\s*[\(\)]", stripped):
                name_match = re.search(r"class\s+(\w+)", stripped)
                if name_match:
                    ann = re.search(r"@(\w+)", stripped)
                    etype = (ann.group(1) if ann else "decorator").lower()
                    elements.append(CodeContext(etype, name_match.group(1), file_path, i, i))
                    continue

            # TypeORM / Prisma models
            if re.search(r"@Entity\s*[\(\)]", stripped):
                name_match = re.search(r"class\s+(\w+)", stripped)
                if name_match:
                    elements.append(CodeContext("model", name_match.group(1), file_path, i, i))
                    continue

        return elements

    @staticmethod
    def parse_javascript(file_path: str, content: str) -> List[CodeContext]:
        return CodeParser.parse_typescript(file_path, content)

    # ── Java ────────────────────────────────────────────────────────────────

    @staticmethod
    def parse_java(file_path: str, content: str) -> List[CodeContext]:
        elements: List[CodeContext] = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Class
            cls_match = re.match(
                r"(?:public\s+|private\s+|protected\s+)?(?:abstract\s+)?(?:class|interface|enum|@interface)\s+(\w+)",
                stripped,
            )
            if cls_match:
                extends = ""
                ext_match = re.search(r"extends\s+(\w+)", stripped)
                if ext_match:
                    extends = ext_match.group(1)
                implements = ""
                imp_match = re.search(r"implements\s+(\w+)", stripped)
                if imp_match:
                    implements = imp_match.group(1)
                elements.append(CodeContext("class", cls_match.group(1), file_path, i, i,
                                            metadata={"extends": extends, "implements": implements}))
                continue

            # Method
            method_match = re.match(
                r"(?:public|private|protected)\s+(?:static\s+)?(?:\w+[\w<>\[\]]+)\s+(\w+)\s*\(", stripped
            )
            if method_match and method_match.group(1) not in ("if", "while", "for", "switch", "catch"):
                elements.append(CodeContext("method", method_match.group(1), file_path, i, i))
                continue

            # Spring annotations
            if stripped.startswith("@") and re.search(r"class\s+(\w+)", stripped):
                name_match = re.search(r"class\s+(\w+)", stripped)
                ann_match = re.match(r"@(\w+)", stripped)
                if name_match and ann_match:
                    elements.append(CodeContext(ann_match.group(1).lower(), name_match.group(1), file_path, i, i))
                    continue

        return elements

    # ── Go ──────────────────────────────────────────────────────────────────

    @staticmethod
    def parse_go(file_path: str, content: str) -> List[CodeContext]:
        elements: List[CodeContext] = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Function
            fn_match = re.match(r"func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(", stripped)
            if fn_match:
                elements.append(CodeContext("function", fn_match.group(1), file_path, i, i))
                continue

            # Struct
            struct_match = re.match(r"type\s+(\w+)\s+struct\s*\{", stripped)
            if struct_match:
                elements.append(CodeContext("struct", struct_match.group(1), file_path, i, i))
                continue

            # Interface
            iface_match = re.match(r"type\s+(\w+)\s+interface\s*\{", stripped)
            if iface_match:
                elements.append(CodeContext("interface", iface_match.group(1), file_path, i, i))
                continue

            # HTTP handler patterns
            if re.search(r"\.(?:GET|POST|PUT|DELETE|PATCH)\s*\(\s*[\"']", stripped):
                route_match = re.search(r"[\"'](\/[^\"']*)[\"']", stripped)
                if route_match:
                    elements.append(CodeContext("route", route_match.group(1), file_path, i, i))
                    continue

        return elements

    # ── Rust ────────────────────────────────────────────────────────────────

    @staticmethod
    def parse_rust(file_path: str, content: str) -> List[CodeContext]:
        elements: List[CodeContext] = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            fn_match = re.match(r"(?:pub\s+)?(?:unsafe\s+)?fn\s+(\w+)", stripped)
            if fn_match:
                elements.append(CodeContext("function", fn_match.group(1), file_path, i, i))
                continue

            struct_match = re.match(r"(?:pub\s+)?struct\s+(\w+)", stripped)
            if struct_match:
                elements.append(CodeContext("struct", struct_match.group(1), file_path, i, i))
                continue

            trait_match = re.match(r"(?:pub\s+)?trait\s+(\w+)", stripped)
            if trait_match:
                elements.append(CodeContext("trait", trait_match.group(1), file_path, i, i))
                continue

            enum_match = re.match(r"(?:pub\s+)?enum\s+(\w+)", stripped)
            if enum_match:
                elements.append(CodeContext("enum", enum_match.group(1), file_path, i, i))
                continue

            impl_match = re.match(r"impl\s+(\w+)", stripped)
            if impl_match:
                elements.append(CodeContext("impl", impl_match.group(1), file_path, i, i))
                continue

        return elements

    # ── Shell ───────────────────────────────────────────────────────────────

    @staticmethod
    def parse_shell(file_path: str, content: str) -> List[CodeContext]:
        elements: List[CodeContext] = []
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            fn_match = re.match(r"function\s+(\w+)\s*(?:\([^)]*\))?\s*\{", stripped) or \
                       re.match(r"^(\w+)\s*\(\s*\)\s*\{", stripped)
            if fn_match:
                elements.append(CodeContext("function", fn_match.group(1), file_path, i, i))
        return elements

    # ── Router ──────────────────────────────────────────────────────────────

    @staticmethod
    def parse(file_path: str, content: str) -> List[CodeContext]:
        ext = Path(file_path).suffix.lower()
        ext_map: Dict[str, Any] = {
            ".py": CodeParser.parse_python,
            ".ts": CodeParser.parse_typescript,
            ".tsx": CodeParser.parse_typescript,
            ".js": CodeParser.parse_javascript,
            ".jsx": CodeParser.parse_javascript,
            ".java": CodeParser.parse_java,
            ".go": CodeParser.parse_go,
            ".rs": CodeParser.parse_rust,
            ".sh": CodeParser.parse_shell,
            ".bash": CodeParser.parse_shell,
        }
        parser = ext_map.get(ext)
        if parser:
            try:
                return parser(file_path, content)
            except Exception as exc:
                log.debug("Parse failed for %s: %s", file_path, exc)
        return []


# =============================================================================
# Part 3 — Dependency Graph
# =============================================================================

class DependencyGraph:
    """Builds and queries dependency relationships between code entities."""

    def __init__(self) -> None:
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._edges: List[Dict[str, Any]] = []

    def add_node(self, node_id: str, node_type: str, name: str,
                 file_path: str = "", metadata: Optional[Dict[str, Any]] = None) -> None:
        if node_id not in self._nodes:
            self._nodes[node_id] = {
                "id": node_id, "type": node_type, "name": name,
                "file_path": file_path, "metadata": metadata or {},
            }

    def add_edge(self, source_id: str, target_id: str, rel_type: str,
                 label: str = "") -> None:
        edge = {
            "source": source_id, "target": target_id,
            "type": rel_type, "label": label or rel_type,
        }
        if edge not in self._edges:
            self._edges.append(edge)

    def add_entities(self, entities: List[CodeContext]) -> None:
        for e in entities:
            nid = e.id
            self.add_node(nid, e.entity_type, e.name, e.file_path)
            for rel in e.relationships:
                self.add_edge(nid, rel["target_id"], rel["type"], rel["target_name"])

    def get_graph(self) -> Dict[str, Any]:
        return {
            "nodes": list(self._nodes.values()),
            "edges": self._edges,
            "node_count": len(self._nodes),
            "edge_count": len(self._edges),
        }

    def get_dependents(self, file_path: str) -> List[str]:
        dependents: List[str] = []
        for edge in self._edges:
            src = self._nodes.get(edge["source"], {})
            if src.get("file_path") != file_path:
                continue
            tgt = self._nodes.get(edge["target"], {})
            if tgt.get("file_path"):
                dependents.append(tgt["file_path"])
        for nid, node in self._nodes.items():
            if node.get("file_path") == file_path:
                for edge in self._edges:
                    if edge["target"] == nid:
                        src = self._nodes.get(edge["source"], {})
                        if src.get("file_path") and src["file_path"] != file_path:
                            dependents.append(src["file_path"])
        return list(set(dependents))

    def to_dict(self) -> Dict[str, Any]:
        return self.get_graph()

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> DependencyGraph:
        g = DependencyGraph()
        g._nodes = {n["id"]: n for n in data.get("nodes", [])}
        g._edges = data.get("edges", [])
        return g


# =============================================================================
# Part 4 — Code Knowledge Graph
# =============================================================================

class CodeKnowledgeGraph:
    """Extends the enterprise knowledge graph with code entities."""

    NODE_LABELS = [
        "Repository", "Package", "Module", "File", "Function",
        "Class", "Interface", "Enum", "Service", "Route", "Model",
        "ReactComponent", "Hook", "Config", "Struct", "Trait",
    ]

    RELATIONSHIP_TYPES = [
        "CONTAINS", "DEPENDS_ON", "CALLS", "EXTENDS", "IMPLEMENTS",
        "DEFINED_IN", "IMPORTS", "EXPORTS", "HAS_ROUTE", "HAS_METHOD",
        "REFERENCES", "COMPOSED_OF",
    ]

    def __init__(self) -> None:
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._relationships: List[Dict[str, Any]] = []
        self._repositories: Dict[str, Dict[str, Any]] = {}

    def record_repository(self, repo_url: str, scan_result: Dict[str, Any]) -> str:
        repo_id = f"repo:{repo_url}"
        self._repositories[repo_id] = {
            "id": repo_id,
            "url": repo_url,
            "name": scan_result.get("directory", "").split("/")[-1] or repo_url.split("/")[-1],
            "languages": scan_result.get("languages", {}),
            "total_files": scan_result.get("total_files", 0),
            "build_systems": scan_result.get("build_systems", []),
            "scanned_at": scan_result.get("scanned_at", ""),
        }
        self._nodes[repo_id] = {
            "id": repo_id, "type": "Repository", "name": repo_url,
            "labels": ["Repository"],
            "properties": self._repositories[repo_id],
        }
        self._emit_graph_event("Repository", repo_id, "created")
        return repo_id

    def record_entities(self, repo_id: str, entities: List[CodeContext],
                        file_paths: Optional[List[str]] = None) -> None:
        file_map: Dict[str, str] = {}
        if file_paths:
            for fp in file_paths:
                fid = f"file:{fp}"
                self._nodes[fid] = {
                    "id": fid, "type": "File", "name": fp,
                    "labels": ["File"],
                    "properties": {"path": fp, "repo_id": repo_id},
                }
                self._add_relationship(repo_id, fid, "CONTAINS")
                file_map[fp] = fid

        for entity in entities:
            nid = f"{entity.entity_type}:{entity.file_path}:{entity.name}"
            node_type = entity.entity_type.capitalize()
            if node_type not in self.NODE_LABELS:
                node_type = "Module" if node_type == "module" else "File"

            self._nodes[nid] = {
                "id": nid,
                "type": node_type,
                "name": entity.name,
                "labels": [node_type],
                "properties": {
                    "file_path": entity.file_path,
                    "line_start": entity.line_start,
                    "line_end": entity.line_end,
                    "docstring": entity.docstring[:200],
                    "metadata": entity.metadata,
                },
            }

            file_id = file_map.get(entity.file_path) or f"file:{entity.file_path}"
            if file_id in self._nodes:
                self._add_relationship(file_id, nid, "DEFINED_IN" if node_type == "File" else "CONTAINS")

            for rel in entity.relationships:
                self._add_relationship(nid, rel["target_id"], rel["type"].upper(),
                                       {"target_name": rel["target_name"]})

        self._emit_graph_event("CodeEntities", repo_id, "updated")

    def _add_relationship(self, source: str, target: str, rel_type: str,
                          properties: Optional[Dict[str, Any]] = None) -> None:
        rel = {
            "source": source, "target": target,
            "type": rel_type, "properties": properties or {},
        }
        if rel not in self._relationships:
            self._relationships.append(rel)

    def query(self, node_type: str = "", name: str = "",
              file_path: str = "") -> List[Dict[str, Any]]:
        results = []
        for node in self._nodes.values():
            if node_type and node.get("type", "").lower() != node_type.lower():
                continue
            if name and name.lower() not in node.get("name", "").lower():
                continue
            props = node.get("properties", {})
            if file_path and file_path not in props.get("file_path", ""):
                continue
            results.append(node)
        return results

    def get_relationships(self, node_id: str) -> List[Dict[str, Any]]:
        return [
            r for r in self._relationships
            if r["source"] == node_id or r["target"] == node_id
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repositories": list(self._repositories.values()),
            "nodes": list(self._nodes.values()),
            "relationships": self._relationships,
        }

    def _emit_graph_event(self, entity_type: str, entity_id: str,
                          action: str = "created") -> None:
        try:
            import asyncio

            from backend.services.enterprise_event_hub import enterprise_hub
            asyncio.ensure_future(enterprise_hub.emit(
                event_type="graph.entity_created",
                agent="code_intelligence",
                status="info",
                message=f"Code Knowledge Graph: {entity_type} {action}",
                execution_id=entity_id,
                metadata={"entity_type": entity_type, "entity_id": entity_id, "action": action},
            ))
        except Exception:
            pass


# =============================================================================
# Part 5 — Impact Analysis
# =============================================================================

class ImpactAnalyzer:
    """Analyzes the impact of changes to a file."""

    RISK_LEVELS = ["low", "medium", "high", "critical"]

    def __init__(self, dep_graph: DependencyGraph, knowledge_graph: CodeKnowledgeGraph) -> None:
        self._dep_graph = dep_graph
        self._kg = knowledge_graph

    def analyze(self, changed_file: str) -> Dict[str, Any]:
        dependents = self._dep_graph.get_dependents(changed_file)

        affected_entities = self._kg.query(file_path=changed_file)
        affected_files: List[str] = [changed_file] + dependents

        affected_apis: List[str] = []
        affected_services: List[str] = []
        affected_models: List[str] = []
        affected_tests: List[str] = []
        affected_frontend: List[str] = []

        for node in self._kg._nodes.values():
            props = node.get("properties", {})
            fp = props.get("file_path", "")
            if not fp or fp not in affected_files:
                continue

            ntype = node.get("type", "").lower()
            if ntype == "route":
                affected_apis.append(node.get("name", ""))
            elif ntype in ("service", "controller"):
                affected_services.append(node.get("name", ""))
            elif ntype == "model":
                affected_models.append(node.get("name", ""))
            elif "test" in fp.lower() or "spec" in fp.lower():
                affected_tests.append(fp)
            elif ntype in ("react_component", "hook", "reactcomponent"):
                affected_frontend.append(node.get("name", ""))

        risk_score = self._calculate_risk(
            len(affected_files), len(affected_apis),
            len(affected_services), len(affected_models),
        )

        return {
            "changed_file": changed_file,
            "risk_score": risk_score,
            "risk_level": self._risk_level(risk_score),
            "directly_affected_files": dependents,
            "all_affected_files": affected_files,
            "affected_apis": list(set(affected_apis)),
            "affected_services": list(set(affected_services)),
            "affected_models": list(set(affected_models)),
            "affected_tests": list(set(affected_tests)),
            "affected_frontend_components": list(set(affected_frontend)),
            "total_affected_entities": len(affected_entities),
            "total_dependents": len(dependents),
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    def _calculate_risk(self, files: int, apis: int, services: int, models: int) -> float:
        score = 0.0
        score += min(files * 5, 30)
        score += min(apis * 10, 30)
        score += min(services * 8, 20)
        score += min(models * 12, 20)
        return min(score, 100)

    def _risk_level(self, score: float) -> str:
        if score >= 70:
            return "critical"
        if score >= 40:
            return "high"
        if score >= 20:
            return "medium"
        return "low"


# =============================================================================
# Enterprise Code Intelligence Engine
# =============================================================================

class EnterpriseCodeIntelligence:
    """
    Understands source code structurally — powering impact analysis,
    intelligent engineering decisions, and autonomous software evolution.
    """

    def __init__(self) -> None:
        self._repositories: Dict[str, Dict[str, Any]] = {}
        self._scanner = RepositoryScanner()
        self._parser = CodeParser()
        self._dep_graph: DependencyGraph = DependencyGraph()
        self._knowledge_graph: CodeKnowledgeGraph = CodeKnowledgeGraph()
        self._impact_analyzer = ImpactAnalyzer(self._dep_graph, self._knowledge_graph)
        self._loaded = False

    # ── Scan ────────────────────────────────────────────────────────────────

    async def scan_repository(self, repo_path: str) -> Dict[str, Any]:
        scan_result = self._scanner.scan(repo_path)
        if "error" in scan_result:
            return scan_result

        repo_id = self._knowledge_graph.record_repository(repo_path, scan_result)

        all_entities: List[CodeContext] = []
        for file_info in scan_result.get("files", []):
            fpath = file_info["path"]
            full_path = os.path.join(repo_path, fpath.replace("/", os.sep))
            if not os.path.isfile(full_path):
                continue
            try:
                with open(full_path, encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception:
                continue
            entities = self._parser.parse(full_path, content)
            for e in entities:
                e.file_path = fpath
            all_entities.extend(entities)

        self._knowledge_graph.record_entities(repo_id, all_entities,
                                               [f["path"] for f in scan_result.get("files", [])])
        self._dep_graph.add_entities(all_entities)

        self._repositories[repo_id] = {
            "id": repo_id,
            "path": repo_path,
            "scan": scan_result,
            "entity_count": len(all_entities),
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

        await self._emit(EET.ENGINEERING_REPO_ANALYZED, repo_id, {
            "path": repo_path,
            "total_files": scan_result.get("total_files", 0),
            "entities": len(all_entities),
            "languages": scan_result.get("languages", {}),
        })

        scan_result["entities"] = [e.to_dict() for e in all_entities]
        scan_result["repo_id"] = repo_id
        scan_result["entity_count"] = len(all_entities)
        return scan_result

    # ── Graph access ────────────────────────────────────────────────────────

    async def get_graph(self, repo_id: str = "") -> Dict[str, Any]:
        if repo_id:
            return self._knowledge_graph.to_dict()
        return self._dep_graph.get_graph()

    async def get_functions(self, repo_id: str = "") -> List[Dict[str, Any]]:
        return self._knowledge_graph.query(node_type="function", name="") + \
               self._knowledge_graph.query(node_type="async_function", name="")

    async def get_classes(self, repo_id: str = "") -> List[Dict[str, Any]]:
        return self._knowledge_graph.query(node_type="class", name="")

    async def get_dependencies(self, node_id: str = "") -> Dict[str, Any]:
        all_rels = self._dep_graph.get_graph()
        if node_id:
            filtered_edges = [
                e for e in all_rels["edges"]
                if e["source"] == node_id or e["target"] == node_id
            ]
            return {"node_id": node_id, "edges": filtered_edges}
        return all_rels

    # ── Impact ──────────────────────────────────────────────────────────────

    async def analyze_impact(self, changed_file: str, repo_id: str = "") -> Dict[str, Any]:
        return self._impact_analyzer.analyze(changed_file)

    # ── Repositories ────────────────────────────────────────────────────────

    async def list_repositories(self) -> List[Dict[str, Any]]:
        return list(self._repositories.values())

    # ── Events ──────────────────────────────────────────────────────────────

    async def _emit(self, event_type: str, repo_id: str,
                     metadata: Optional[Dict[str, Any]] = None) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type=event_type,
                agent="code_intelligence",
                status="info",
                message=f"Code Intelligence: {event_type.split('.')[-1]}",
                execution_id=repo_id,
                metadata={"repo_id": repo_id, "domain": "code_intelligence", **(metadata or {})},
            )
        except Exception as exc:
            log.debug("Code Intelligence event emit failed: %s", exc)


# =============================================================================
# Singleton
# =============================================================================

code_intelligence = EnterpriseCodeIntelligence()
