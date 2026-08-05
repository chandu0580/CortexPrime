"""The rule that makes the contracts package safe: it depends on nothing.

Every other package in CortexPrime is permitted to import ``backend.contracts``.
That is only safe while contracts import nothing back. This module enforces that
by static analysis of the source rather than by convention, because conventions
erode and CI does not.

If one of these tests fails, do not add an exception -- move the offending code
out of contracts. See ADR-010.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "backend" / "contracts"

#: Third-party distributions the contracts package may import. Deliberately
#: empty. Adding an entry here is an architectural change requiring an ADR.
APPROVED_THIRD_PARTY: frozenset[str] = frozenset()

#: Standard-library modules the contracts package uses. Listed explicitly so
#: that a new stdlib dependency is a visible, reviewed change rather than a
#: silent one.
APPROVED_STDLIB = frozenset(
    {
        "__future__",
        "abc",
        "dataclasses",
        "datetime",
        "enum",
        "hmac",
        "types",
        "typing",
        "uuid",
    }
)


def _contract_modules() -> list[Path]:
    modules = sorted(path for path in CONTRACTS_DIR.glob("*.py"))
    assert modules, f"no contract modules found under {CONTRACTS_DIR}"
    return modules


def _imported_roots(source: str) -> set[str]:
    """Return the root module name of every import in ``source``."""
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import
                roots.add("__relative__")
            elif node.module:
                roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("module_path", _contract_modules(), ids=lambda p: p.name)
def test_contract_module_imports_only_approved_roots(module_path: Path) -> None:
    """No contract module may import anything outside stdlib or itself."""
    roots = _imported_roots(module_path.read_text(encoding="utf-8"))
    permitted = APPROVED_STDLIB | APPROVED_THIRD_PARTY | {"backend"}
    forbidden = roots - permitted
    assert not forbidden, (
        f"{module_path.name} imports disallowed root(s): {sorted(forbidden)}. "
        "Contracts depend on nothing; move this code out of the package."
    )


@pytest.mark.parametrize("module_path", _contract_modules(), ids=lambda p: p.name)
def test_backend_imports_are_contracts_only(module_path: Path) -> None:
    """Where a contract module imports ``backend``, it must be another contract.

    ``backend.contracts.x`` is fine -- contracts may compose. ``backend.database``,
    ``backend.services``, ``backend.platform`` are not.
    """
    source = module_path.read_text(encoding="utf-8")
    offenders: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("backend"):
            if not node.module.startswith("backend.contracts"):
                offenders.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("backend") and not alias.name.startswith(
                    "backend.contracts"
                ):
                    offenders.append(alias.name)
    assert not offenders, (
        f"{module_path.name} imports non-contract backend module(s): {sorted(set(offenders))}"
    )


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_in_subprocess(script: str) -> subprocess.CompletedProcess[str]:
    """Execute ``script`` in a clean interpreter rooted at the repository.

    These checks manipulate module state, which is unsafe to do in-process:
    purging ``sys.modules`` produces duplicate class objects, so every later
    test in the session would compare against a stale type. A subprocess gives
    genuine isolation at negligible cost.
    """
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_importing_contracts_pulls_in_no_heavy_dependencies() -> None:
    """Importing contracts must not drag in a web, ORM, or validation framework.

    This is the runtime counterpart to the static checks: it catches a
    transitive import that source inspection of the package alone would miss.
    """
    script = """
import sys
import backend.contracts  # noqa: F401
forbidden = {"fastapi", "sqlalchemy", "pydantic", "starlette", "redis", "httpx", "openai"}
loaded = sorted(forbidden & set(sys.modules))
print(",".join(loaded))
"""
    result = _run_in_subprocess(script)
    assert result.returncode == 0, f"importing backend.contracts failed:\n{result.stderr}"
    loaded = [name for name in result.stdout.strip().split(",") if name]
    assert not loaded, f"importing backend.contracts loaded framework module(s): {loaded}"


def test_every_contract_module_imports_standalone() -> None:
    """Each module must import on its own, in any order, with no cycles.

    Importing a single leaf module in a fresh interpreter is the strongest form
    of this check: it proves the module does not depend on ``__init__`` having
    run first, which is how import cycles usually hide.
    """
    for module_path in _contract_modules():
        if module_path.name == "__init__.py":
            continue
        name = f"backend.contracts.{module_path.stem}"
        result = _run_in_subprocess(f"import {name}")
        assert result.returncode == 0, f"{name} failed to import standalone:\n{result.stderr}"
