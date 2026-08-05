"""The file-state guard: no *new* authoritative state in local files.

The load-bearing test is `test_a_new_json_store_fails`. Everything else exists
to keep that one from being defeated by a false positive — a rule that flags
config reads or test fixtures gets exceptions added until it flags nothing.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from backend.platform.architecture import (
    APPROVED_STORES,
    GRANDFATHERED_STORES,
    FileStateRule,
    ModuleGraph,
    Severity,
    default_suite,
    render_text,
    scan_state_files,
)
from tests.architecture.probes import SERVICE_LEVEL_PROBES

REPO_BACKEND = Path(__file__).resolve().parents[2] / "backend"


def tree(root: Path, files: dict[str, str]) -> ModuleGraph:
    for relative, source in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source), encoding="utf-8")
    return ModuleGraph.build(root, package_root=root.name)


@pytest.fixture
def rule() -> FileStateRule:
    return FileStateRule(grandfathered=GRANDFATHERED_STORES)


# ======================================================================
# The rule does its job
# ======================================================================


class TestNewStoresFail:
    def test_a_new_json_store_fails(self, rule, tmp_path) -> None:
        """The reason this rule exists."""
        graph = tree(
            tmp_path / "pkg",
            {
                "service.py": """
                import json

                def save(data):
                    with open("brand_new_store.json", "w") as handle:
                        json.dump(data, handle)
                """
            },
        )
        result = rule.evaluate(graph)
        assert not result.passed
        assert result.blocking_violations
        violation = result.blocking_violations[0]
        assert violation.offender == "brand_new_store.json"
        assert violation.severity is Severity.ERROR
        assert "NEW file-based authoritative state" in violation.detail

    @pytest.mark.parametrize(
        "filename,writer",
        [
            ("new_store.json", "import json\njson.dump({}, open('new_store.json','w'))"),
            ("new_store.yaml", "import yaml\nyaml.dump({}, open('new_store.yaml','w'))"),
            ("new_store.pkl", "import pickle\npickle.dump({}, open('new_store.pkl','wb'))"),
            ("new_store.csv", "import csv\nopen('new_store.csv','w').writelines([])"),
            ("new_store.toml", "import toml\ntoml.dump({}, open('new_store.toml','w'))"),
            ("new_store.jsonl", "open('new_store.jsonl','a').writelines(['x'])"),
            ("new_store.db", "import sqlite3\nsqlite3.connect('new_store.db')"),
            ("new_store.dat", "from pathlib import Path\nPath('new_store.dat').write_bytes(b'')"),
        ],
    )
    def test_every_persistence_format_is_detected(
        self, rule, tmp_path, filename: str, writer: str
    ) -> None:
        graph = tree(tmp_path / f"pkg_{filename.replace('.', '_')}", {"s.py": writer})
        result = rule.evaluate(graph)
        offenders = {v.offender for v in result.blocking_violations}
        assert filename in offenders, f"{filename} was not detected"

    def test_append_mode_is_detected(self, rule, tmp_path) -> None:
        """Append is still authoritative state, just accumulating."""
        graph = tree(
            tmp_path / "pkg",
            {"s.py": "import json\nwith open('appended.json','a') as h:\n    json.dump({}, h)\n"},
        )
        assert "appended.json" in {v.offender for v in rule.evaluate(graph).blocking_violations}

    def test_violation_reports_module_and_line(self, rule, tmp_path) -> None:
        graph = tree(
            tmp_path / "pkg",
            {"deep/nested/svc.py": "import json\n\n\njson.dump({}, open('x_store.json','w'))\n"},
        )
        violation = rule.evaluate(graph).blocking_violations[0]
        assert violation.module == "pkg.deep.nested.svc"
        assert violation.line == 4

    def test_violation_suggests_a_migration(self, rule, tmp_path) -> None:
        """A violation without a remedy makes deleting the rule the cheap fix."""
        graph = tree(
            tmp_path / "pkg", {"s.py": "import json\njson.dump({}, open('x.json','w'))\n"}
        )
        detail = rule.evaluate(graph).blocking_violations[0].detail
        assert "repository" in detail
        assert "transactional store" in detail


# ======================================================================
# Approved and grandfathered stores warn, never block
# ======================================================================


class TestApprovedAndGrandfathered:
    @pytest.mark.parametrize("filename", sorted(APPROVED_STORES))
    def test_approved_stores_warn_only(self, rule, tmp_path, filename: str) -> None:
        graph = tree(
            tmp_path / f"pkg_{filename.replace('.', '_')}",
            {"s.py": f"import json\njson.dump({{}}, open('{filename}','w'))\n"},
        )
        result = rule.evaluate(graph)
        assert result.passed, "an approved store must not block the gate"
        assert result.warnings
        assert "pending PR-11 migration" in result.warnings[0].detail

    def test_grandfathered_store_warns_only(self, rule, tmp_path) -> None:
        graph = tree(
            tmp_path / "pkg",
            {"s.py": "import json\njson.dump({}, open('runtime_store.json','w'))\n"},
        )
        result = rule.evaluate(graph)
        assert result.passed
        assert "grandfathered" in result.warnings[0].detail

    def test_the_real_repository_passes(self) -> None:
        """Every existing store is accounted for; the gate is green today."""
        graph = ModuleGraph.build(REPO_BACKEND)
        result = FileStateRule(grandfathered=GRANDFATHERED_STORES).evaluate(graph)
        assert result.passed, "\n".join(
            str(v) for v in result.blocking_violations[:20]
        )

    def test_the_inventory_covers_what_exists(self) -> None:
        """Guards against the inventory drifting out of date silently."""
        graph = ModuleGraph.build(REPO_BACKEND)
        detected = {write.filename for write in scan_state_files(graph)}
        uncovered = detected - APPROVED_STORES - GRANDFATHERED_STORES
        assert not uncovered, f"stores not in the inventory: {sorted(uncovered)}"

    def test_approved_and_grandfathered_do_not_overlap(self) -> None:
        """The three approved stores are tracked separately, not buried."""
        assert not (APPROVED_STORES & GRANDFATHERED_STORES)

    def test_inventory_is_frozen(self) -> None:
        assert isinstance(GRANDFATHERED_STORES, frozenset)
        assert isinstance(APPROVED_STORES, frozenset)


# ======================================================================
# What must be ignored
# ======================================================================


class TestExclusions:
    def test_test_files_are_ignored(self, rule, tmp_path) -> None:
        graph = tree(
            tmp_path / "pkg",
            {"test_thing.py": "import json\njson.dump({}, open('fixture_data.json','w'))\n"},
        )
        assert rule.evaluate(graph).passed

    def test_test_directories_are_ignored(self, rule, tmp_path) -> None:
        graph = tree(
            tmp_path / "pkg",
            {"tests/helper.py": "import json\njson.dump({}, open('some_data.json','w'))\n"},
        )
        assert rule.evaluate(graph).passed

    def test_conftest_is_ignored(self, rule, tmp_path) -> None:
        graph = tree(
            tmp_path / "pkg",
            {"conftest.py": "import json\njson.dump({}, open('state.json','w'))\n"},
        )
        assert rule.evaluate(graph).passed

    @pytest.mark.parametrize("folder", ["fixtures", "samples", "examples", "docs", "scripts"])
    def test_non_operational_directories_are_ignored(
        self, rule, tmp_path, folder: str
    ) -> None:
        graph = tree(
            tmp_path / f"pkg_{folder}",
            {f"{folder}/thing.py": "import json\njson.dump({}, open('data.json','w'))\n"},
        )
        assert rule.evaluate(graph).passed

    def test_migrations_are_ignored(self, rule, tmp_path) -> None:
        graph = tree(
            tmp_path / "pkg",
            {"migrations/v1.py": "import json\njson.dump({}, open('seed.json','w'))\n"},
        )
        assert rule.evaluate(graph).passed

    @pytest.mark.parametrize(
        "filename",
        ["pyproject.toml", "package.json", "tsconfig.json", "docker-compose.yml",
         "config.yaml", ".gitlab-ci.yml", "Cargo.toml", "openapi.json"],
    )
    def test_configuration_filenames_are_ignored(
        self, rule, tmp_path, filename: str
    ) -> None:
        """These appear as literals a connector *looks for*, not state we write."""
        safe = filename.replace(".", "_").replace("-", "_")
        graph = tree(
            tmp_path / f"pkg_{safe}",
            {"s.py": f"from pathlib import Path\nPath('{filename}').write_text('x')\n"},
        )
        assert rule.evaluate(graph).passed, f"{filename} was flagged as state"

    def test_reading_a_json_file_is_not_flagged(self, rule, tmp_path) -> None:
        """Only writes matter. Reading configuration is ordinary and fine."""
        graph = tree(
            tmp_path / "pkg",
            {"s.py": "import json\ndata = json.load(open('lookup_table.json'))\n"},
        )
        assert rule.evaluate(graph).passed

    def test_runtime_assembled_filenames_are_not_flagged(self, rule, tmp_path) -> None:
        """A format placeholder names nothing; flagging it is noise."""
        graph = tree(
            tmp_path / "pkg",
            {"s.py": "import json\njson.dump({}, open('{}.json'.format('x'),'w'))\n"},
        )
        assert not any(
            v.offender == "{}.json" for v in rule.evaluate(graph).violations
        )

    def test_a_module_with_no_writes_is_not_flagged(self, rule, tmp_path) -> None:
        graph = tree(tmp_path / "pkg", {"s.py": "PATH = 'some_store.json'\n"})
        assert rule.evaluate(graph).passed


# ======================================================================
# Integration with the gate
# ======================================================================


class TestSuiteIntegration:
    def test_rule_is_part_of_the_default_suite(self) -> None:
        rule_ids = {rule.rule_id for rule in default_suite().rules}
        assert "STATE-NO-NEW-FILE-STORES" in rule_ids

    def test_gate_still_passes_with_the_rule_active(self) -> None:
        graph = ModuleGraph.build(REPO_BACKEND)
        result = default_suite(SERVICE_LEVEL_PROBES).run(graph)
        assert result.gate_passed, "\n".join(
            str(v) for v in result.blocking_violations[:20]
        )

    def test_a_new_store_would_fail_the_whole_gate(self, tmp_path) -> None:
        """End to end: a new store blocks the merge, not just the rule."""
        from backend.platform.architecture import ArchitectureSuite

        graph = tree(
            tmp_path / "pkg",
            {"s.py": "import json\njson.dump({}, open('sneaky_new_store.json','w'))\n"},
        )
        suite = ArchitectureSuite(rules=(FileStateRule(grandfathered=GRANDFATHERED_STORES),))
        result = suite.run(graph)
        assert not result.gate_passed
        assert "sneaky_new_store.json" in render_text(result)

    def test_report_separates_warnings_from_failures(self, tmp_path) -> None:
        from backend.platform.architecture import ArchitectureSuite

        graph = tree(
            tmp_path / "pkg",
            {
                "new.py": "import json\njson.dump({}, open('brand_new.json','w'))\n",
                "old.py": "import json\njson.dump({}, open('runtime_store.json','w'))\n",
            },
        )
        suite = ArchitectureSuite(rules=(FileStateRule(grandfathered=GRANDFATHERED_STORES),))
        result = suite.run(graph)
        assert len(result.blocking_violations) == 1
        assert result.blocking_violations[0].offender == "brand_new.json"
        assert any(v.offender == "runtime_store.json" for v in result.all_warnings)
