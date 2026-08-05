"""Platform's dependency rule, enforced by static analysis.

Constitution S10::

    platform/  may import  contracts/
    platform/  may NOT import  contexts/  or  legacy/

Platform code knows *how*, never *why*. A module here that can name a detector,
a mission type, or a customer has drifted into a bounded context.

The identity and hashing modules additionally take no third-party dependency at
all: ULID is implemented against its specification rather than pulled in, per
Constitution S11 ("every dependency needs a named owner and a stated reason").
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_DIR = REPO_ROOT / "backend" / "platform"

#: Third-party distributions these modules may import. Deliberately empty.
#: Adding an entry is an architectural change requiring an ADR.
APPROVED_THIRD_PARTY: frozenset[str] = frozenset()

#: Standard-library modules platform may use. Listed explicitly so that a new
#: stdlib dependency is a visible, reviewed change rather than a silent one.
APPROVED_STDLIB = frozenset(
    {
        "__future__",
        "argparse",
        "ast",
        "dataclasses",
        "datetime",
        "enum",
        "hashlib",
        "hmac",
        "json",
        "math",
        "os",
        "pathlib",
        "re",
        "sys",
        "threading",
        "time",
        "types",
        "typing",
        "uuid",
    }
)

FORBIDDEN_BACKEND_ROOTS = ("backend.contexts", "backend.legacy", "backend.services", "backend.api")


def _platform_modules() -> list[Path]:
    modules = sorted(PLATFORM_DIR.rglob("*.py"))
    assert modules, f"no platform modules found under {PLATFORM_DIR}"
    return modules


def _module_id(path: Path) -> str:
    return str(path.relative_to(PLATFORM_DIR))


@pytest.mark.parametrize("module_path", _platform_modules(), ids=_module_id)
def test_imports_only_approved_roots(module_path: Path) -> None:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(module_path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])

    permitted = APPROVED_STDLIB | APPROVED_THIRD_PARTY | {"backend"}
    forbidden = roots - permitted
    assert not forbidden, (
        f"{_module_id(module_path)} imports disallowed root(s): {sorted(forbidden)}"
    )


@pytest.mark.parametrize("module_path", _platform_modules(), ids=_module_id)
def test_does_not_import_a_bounded_context(module_path: Path) -> None:
    source = module_path.read_text(encoding="utf-8")
    offenders: list[str] = []
    for node in ast.walk(ast.parse(source)):
        names: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        offenders.extend(
            name for name in names if name.startswith(FORBIDDEN_BACKEND_ROOTS)
        )
    assert not offenders, (
        f"{_module_id(module_path)} imports bounded-context module(s): {sorted(set(offenders))}"
    )


def test_importing_platform_pulls_in_no_frameworks() -> None:
    script = """
import sys
import backend.platform.hashing
import backend.platform.identity
forbidden = {"fastapi", "sqlalchemy", "pydantic", "starlette", "redis", "httpx", "openai"}
print(",".join(sorted(forbidden & set(sys.modules))))
"""
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=REPO_ROOT, capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    loaded = [name for name in result.stdout.strip().split(",") if name]
    assert not loaded, f"importing platform loaded framework module(s): {loaded}"


def test_every_module_imports_standalone() -> None:
    """Proves there are no import cycles within platform."""
    for module_path in _platform_modules():
        if module_path.name == "__init__.py":
            continue
        relative = module_path.relative_to(REPO_ROOT).with_suffix("")
        name = ".".join(relative.parts)
        result = subprocess.run(
            [sys.executable, "-c", f"import {name}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"{name} failed to import standalone:\n{result.stderr}"


def test_no_third_party_dependency_was_introduced() -> None:
    """ULID is implemented, not imported. This guards that decision."""
    assert APPROVED_THIRD_PARTY == frozenset(), (
        "a third-party dependency was added to platform identity/hashing; "
        "this requires an ADR superseding ADR-011"
    )
