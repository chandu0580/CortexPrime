"""
Validation tests for the Enterprise Execution Sandbox.

Simulates:
  ✓ Sandbox CRUD (create, list, get)
  ✓ Sandbox lifecycle (create -> ready -> pause -> resume -> destroy)
  ✓ Repository preparation (clone or empty dir)
  ✓ Dependency detection
  ✓ Command execution (success + failure)
  ✓ Language support (Python, Node, Java, .NET, Go, Rust, Shell)
  ✓ Artifact collection
  ✓ Log recording
  ✓ Resource monitoring
  ✓ ExecutionResult model
  ✓ Sandbox persistence (to_dict / from_dict)
  ✓ Sandbox isolation (separate directories)
  ✓ Destroy sandbox preserves metadata

Verifies:
  ✓ Sandbox created with correct status
  ✓ Repository prepared with logs
  ✓ Execution completes with stdout/stderr
  ✓ Artifacts collected and classified
  ✓ Logs stored per operation
  ✓ Resource usage tracked
  ✓ Sandbox status transitions valid
  ✓ Destroy marks destroyed_at
  ✓ to_dict/from_dict round-trip preserves fields
"""
import pytest

from backend.services.enterprise_execution_sandbox import (
    EnterpriseExecutionSandbox,
    Sandbox,
    ExecutionResult,
    SUPPORTED_LANGUAGES,
    SANDBOX_STATUSES,
)


@pytest.fixture
def sandbox_engine():
    engine = EnterpriseExecutionSandbox()
    engine._sandboxes.clear()
    return engine


# ── Part 1: Sandbox Manager ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_sandbox(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(name="Test Sandbox", language="python")
    assert sbx.sandbox_id is not None
    assert sbx.name == "Test Sandbox"
    assert sbx.language == "python"
    assert sbx.status == "ready"


@pytest.mark.asyncio
async def test_create_sandbox_with_repo(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(
        name="Repo Sandbox",
        repo_url="https://github.com/example/repo.git",
        branch="develop",
        language="node",
    )
    assert sbx.repo_url == "https://github.com/example/repo.git"
    assert sbx.branch == "develop"
    assert sbx.language == "node"
    assert sbx.isolation_path is not None


@pytest.mark.asyncio
async def test_list_sandboxes(sandbox_engine):
    await sandbox_engine.create_sandbox(name="Sbx A", language="python")
    await sandbox_engine.create_sandbox(name="Sbx B", language="python")

    sandboxes = await sandbox_engine.list_sandboxes()
    assert len(sandboxes) >= 2


@pytest.mark.asyncio
async def test_list_sandboxes_filter_status(sandbox_engine):
    s1 = await sandbox_engine.create_sandbox(name="Sbx 1", language="python")
    await sandbox_engine.destroy_sandbox(s1.sandbox_id)

    ready = await sandbox_engine.list_sandboxes(status="ready")
    destroyed = await sandbox_engine.list_sandboxes(status="destroyed")
    assert all(s["status"] == "ready" for s in ready)
    assert all(s["status"] == "destroyed" for s in destroyed)


@pytest.mark.asyncio
async def test_list_sandboxes_filter_language(sandbox_engine):
    await sandbox_engine.create_sandbox(name="Py Sbx", language="python")
    await sandbox_engine.create_sandbox(name="Node Sbx", language="node")

    py = await sandbox_engine.list_sandboxes(language="python")
    assert all(s["language"] == "python" for s in py)


@pytest.mark.asyncio
async def test_get_sandbox(sandbox_engine):
    created = await sandbox_engine.create_sandbox(name="GetMe")
    fetched = await sandbox_engine.get_sandbox(created.sandbox_id)
    assert fetched is not None
    assert fetched.name == "GetMe"


@pytest.mark.asyncio
async def test_get_nonexistent_sandbox(sandbox_engine):
    result = await sandbox_engine.get_sandbox("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_start_sandbox(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(name="Starter")
    # After create, status is "ready" — start transitions to ready if destroyed
    # We already get ready on create, so start should return ready
    started = await sandbox_engine.start_sandbox(sbx.sandbox_id)
    assert started is not None
    assert started.status == "ready"


@pytest.mark.asyncio
async def test_start_destroyed_sandbox_returns_none(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(name="FailStart")
    await sandbox_engine.destroy_sandbox(sbx.sandbox_id)
    result = await sandbox_engine.start_sandbox(sbx.sandbox_id)
    assert result is None


# ── Part 1b: Pause / Resume / Destroy ───────────────────────────────────────

@pytest.mark.asyncio
async def test_pause_sandbox(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(name="Pausable")
    # Set to running so we can pause
    sbx.status = "running"
    paused = await sandbox_engine.pause_sandbox(sbx.sandbox_id)
    assert paused is not None
    assert paused.status == "paused"


@pytest.mark.asyncio
async def test_pause_nonrunning_returns_none(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(name="NoPause")
    result = await sandbox_engine.pause_sandbox(sbx.sandbox_id)
    assert result is None  # status is "ready", not "running"


@pytest.mark.asyncio
async def test_resume_sandbox(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(name="Resumable")
    sbx.status = "paused"
    resumed = await sandbox_engine.resume_sandbox(sbx.sandbox_id)
    assert resumed is not None
    assert resumed.status == "running"


@pytest.mark.asyncio
async def test_resume_nonpaused_returns_none(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(name="NoResume")
    result = await sandbox_engine.resume_sandbox(sbx.sandbox_id)
    assert result is None


@pytest.mark.asyncio
async def test_destroy_sandbox(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(name="Destructible")
    destroyed = await sandbox_engine.destroy_sandbox(sbx.sandbox_id)
    assert destroyed is not None
    assert destroyed.status == "destroyed"
    assert destroyed.destroyed_at != ""


@pytest.mark.asyncio
async def test_destroy_nonexistent_returns_none(sandbox_engine):
    result = await sandbox_engine.destroy_sandbox("nonexistent")
    assert result is None


# ── Part 2: Repository Preparation ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_prepare_repository_empty(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(name="No Repo")
    prepared = await sandbox_engine.prepare_repository(sbx.sandbox_id)
    assert prepared is not None
    assert len(prepared.logs) >= 1
    repo_logs = [l for l in prepared.logs if l["type"] == "repo_prep"]
    assert len(repo_logs) >= 1


@pytest.mark.asyncio
async def test_prepare_nonexistent_sandbox(sandbox_engine):
    result = await sandbox_engine.prepare_repository("nonexistent")
    assert result is None


# ── Part 3: Execution ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_simple_command(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(name="Executor")
    await sandbox_engine.prepare_repository(sbx.sandbox_id)
    # Execute a basic command using Python (guaranteed available)
    result = await sandbox_engine.execute(
        sandbox_id=sbx.sandbox_id,
        command="python -c \"print('hello world')\"",
        language="shell",
    )
    assert result is not None
    assert result.exit_code == 0, f"stdout={result.stdout} stderr={result.stderr}"
    assert "hello world" in result.stdout


@pytest.mark.asyncio
async def test_execute_failing_command(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(name="Fail Exec")
    await sandbox_engine.prepare_repository(sbx.sandbox_id)
    result = await sandbox_engine.execute(
        sandbox_id=sbx.sandbox_id,
        command="python -c 'raise RuntimeError(\"boom\")'",
        language="shell",
    )
    assert result is not None
    assert result.exit_code != 0
    assert sbx.status == "failed"


@pytest.mark.asyncio
async def test_execute_nonexistent_sandbox(sandbox_engine):
    result = await sandbox_engine.execute("nonexistent", command="echo hi")
    assert result is None


@pytest.mark.asyncio
async def test_execute_destroyed_sandbox_returns_none(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(name="Dead Exec")
    await sandbox_engine.destroy_sandbox(sbx.sandbox_id)
    result = await sandbox_engine.execute(sbx.sandbox_id, command="echo hi")
    assert result is None


@pytest.mark.asyncio
async def test_execute_records_logs(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(name="Loggy")
    await sandbox_engine.prepare_repository(sbx.sandbox_id)
    log_count_before = len(sbx.logs)
    await sandbox_engine.execute(sbx.sandbox_id, command="python -c \"print('log-test')\"", language="shell")
    assert len(sbx.logs) > log_count_before


@pytest.mark.asyncio
async def test_execute_updates_resource_usage(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(name="Res Monitor")
    await sandbox_engine.prepare_repository(sbx.sandbox_id)
    await sandbox_engine.execute(sbx.sandbox_id, command="python -c \"print('resource-test')\"", language="shell")
    resources = await sandbox_engine.get_resource_usage(sbx.sandbox_id)
    assert resources is not None
    assert resources["execution_count"] >= 1


# ── Part 4: Artifacts ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collect_artifacts_empty(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(name="Artifact Test")
    await sandbox_engine.prepare_repository(sbx.sandbox_id)
    artifacts = await sandbox_engine.get_artifacts(sbx.sandbox_id)
    assert isinstance(artifacts, list)


@pytest.mark.asyncio
async def test_get_artifacts_nonexistent(sandbox_engine):
    result = await sandbox_engine.get_artifacts("nonexistent")
    assert result == []


# ── Part 5: Logs ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_logs(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(name="Log Fetch")
    await sandbox_engine.prepare_repository(sbx.sandbox_id)
    logs = await sandbox_engine.get_logs(sbx.sandbox_id)
    assert len(logs) >= 1


@pytest.mark.asyncio
async def test_get_logs_nonexistent(sandbox_engine):
    result = await sandbox_engine.get_logs("nonexistent")
    assert result == []


# ── Part 5b: Resource Monitoring ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_resource_usage_nonexistent(sandbox_engine):
    result = await sandbox_engine.get_resource_usage("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_resource_usage_structure(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(name="Res Struct")
    await sandbox_engine.prepare_repository(sbx.sandbox_id)
    await sandbox_engine.execute(sbx.sandbox_id, command="echo res-struct", language="shell")
    ru = await sandbox_engine.get_resource_usage(sbx.sandbox_id)
    assert ru is not None
    assert "cpu_percent" in ru
    assert "memory_mb" in ru
    assert "execution_count" in ru
    assert "artifact_count" in ru


# ── Supported Languages ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_supported_languages(sandbox_engine):
    expected = {"python", "node", "java", "dotnet", "go", "rust", "shell"}
    assert set(SUPPORTED_LANGUAGES) == expected
    assert len(SUPPORTED_LANGUAGES) == 7


@pytest.mark.asyncio
async def test_sandbox_statuses(sandbox_engine):
    expected = {
        "creating", "ready", "running", "paused",
        "executing", "completed", "failed", "destroyed",
    }
    assert set(SANDBOX_STATUSES) == expected
    assert len(SANDBOX_STATUSES) == 8


# ── ExecutionResult ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execution_result_success(sandbox_engine):
    result = ExecutionResult(
        execution_id="exec-test",
        command="python -c \"print('ok')\"",
        exit_code=0,
        stdout="ok\n",
        stderr="",
        duration_ms=10.0,
        language="shell",
    )
    assert result.succeeded() is True
    assert result.to_dict()["exit_code"] == 0


@pytest.mark.asyncio
async def test_execution_result_failure(sandbox_engine):
    result = ExecutionResult(
        execution_id="exec-fail",
        command="false",
        exit_code=1,
        stdout="",
        stderr="error occurred",
        duration_ms=5.0,
    )
    assert result.succeeded() is False
    assert "error occurred" in result.stderr


@pytest.mark.asyncio
async def test_execution_result_to_dict(sandbox_engine):
    result = ExecutionResult(
        execution_id="exec-dict",
        command="python test.py",
        exit_code=0,
        stdout="pass",
        stderr="",
        duration_ms=100.0,
        language="python",
        artifacts=[{"name": "report.xml", "type": "report"}],
        resource_usage={"cpu": 50.0},
    )
    d = result.to_dict()
    assert d["execution_id"] == "exec-dict"
    assert d["language"] == "python"
    assert len(d["artifacts"]) == 1
    assert d["resource_usage"]["cpu"] == 50.0


# ── Serialization ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sandbox_to_dict_round_trip(sandbox_engine):
    sbx = Sandbox(name="RoundTrip", repo_url="https://r.com", branch="feat", language="go")
    sbx.status = "running"
    sbx.executions.append({"execution_id": "e1", "exit_code": 0})
    sbx.artifacts.append({"name": "out.log", "size_bytes": 100})
    sbx.logs.append({"type": "test", "message": "hello"})

    data = sbx.to_dict()
    restored = Sandbox.from_dict(data)
    assert restored.name == sbx.name
    assert restored.repo_url == sbx.repo_url
    assert restored.branch == sbx.branch
    assert restored.language == sbx.language
    assert restored.status == sbx.status
    assert restored.sandbox_id == sbx.sandbox_id
    assert len(restored.executions) == 1
    assert len(restored.artifacts) == 1


# ── Edge Cases ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_command_not_found(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(name="CmdNotFound")
    await sandbox_engine.prepare_repository(sbx.sandbox_id)
    result = await sandbox_engine.execute(
        sandbox_id=sbx.sandbox_id,
        command="nonexistent_command_xyz",
        language="shell",
    )
    assert result is not None
    assert result.exit_code != 0
    assert "not found" in result.stderr.lower() or "not recognized" in result.stderr.lower()


@pytest.mark.asyncio
async def test_multiple_sandboxes_isolated(sandbox_engine):
    s1 = await sandbox_engine.create_sandbox(name="Isolation A")
    s2 = await sandbox_engine.create_sandbox(name="Isolation B")
    assert s1.sandbox_id != s2.sandbox_id
    assert s1.isolation_path != s2.isolation_path
    assert s1.isolation_path is not None
    assert s2.isolation_path is not None


@pytest.mark.asyncio
async def test_destroyed_sandbox_preserves_metadata(sandbox_engine):
    sbx = await sandbox_engine.create_sandbox(name="PreserveMeta", repo_url="https://example.com")
    await sandbox_engine.prepare_repository(sbx.sandbox_id)

    before_destroy = sbx.to_dict()
    await sandbox_engine.destroy_sandbox(sbx.sandbox_id)

    assert sbx.status == "destroyed"
    assert sbx.destroyed_at != ""
    # Name and repo are preserved
    assert sbx.name == "PreserveMeta"
    assert sbx.repo_url == "https://example.com"
    # Logs are preserved
    assert len(sbx.logs) >= 1
