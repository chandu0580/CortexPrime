"""Phase 11.3 (ADR-123 D-19): "that evidence does not exist" is absence, not a block.

Measured on the live cluster: asked for a container's previous log, the API
server answered with an error -- ``previous terminated container "app" in pod
... not found`` -- where in other runs the kubelet answered 200 with the same
text. The failed read blocked the OOM investigation. A tool may declare which
failure reasons mean the evidence does not exist; everything else still blocks.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.api.governed_evidence_acquisition import (
    GovernedEvidenceAcquisition, InvestigationTool, ToolRegistry,
)
from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
    _LOG_UNAVAILABLE, kubernetes_read_catalog,
)
from backend.contracts.errors import ContractViolation

POD = "kubernetes:pod:cortex-p113/p113-oom-5689f87844-dgb9x"
GONE = 'previous terminated container "app" in pod "p113-oom-5689f87844-dgb9x" not found'


class _FailingReader:
    def __init__(self, reason: str):
        self.reason, self.calls = reason, 0

    def read(self, context, *, operation, payload):
        self.calls += 1
        return SimpleNamespace(succeeded=False, failure_reason=self.reason, evidence={})


def _log_tool(*, absent_when=_LOG_UNAVAILABLE) -> InvestigationTool:
    return InvestigationTool(
        key="k8s.pod_logs_previous", operation="kubernetes.pod.logs",
        subject_kind="kubernetes:pod:", predicate="log_patterns_previous",
        describes="the previous container instance log", project=lambda e: e,
        source_ref="kubelet:container-logs",
        payload_from_subject=lambda s: {"namespace": "cortex-p113", "name": "p113-oom-5689f87844-dgb9x",
                                        "previous": True, "tailLines": 200},
        absent_when=absent_when)


def _acquire(tool: InvestigationTool, reason: str):
    registry = ToolRegistry(tools=(tool,), catalogs={"kubernetes": kubernetes_read_catalog()})
    reader = _FailingReader(reason)
    port = GovernedEvidenceAcquisition(reader=reader, observer=object(), derivation=None,
                                       registry=registry, context=object())
    request = SimpleNamespace(tool=tool.key, subject_ref=POD, predicate=tool.predicate, read_only=True)
    result = port.acquire(tenant=object(), request=request, now=datetime.now(timezone.utc))
    return result, reader


def test_a_declared_missing_log_is_absence_not_a_block():
    result, reader = _acquire(_log_tool(), GONE)
    assert reader.calls == 1
    assert result.ok is False and result.absent is True
    assert "does not exist" in result.reason


def test_any_other_failure_still_blocks():
    result, _ = _acquire(_log_tool(), "authorization refused: capability not granted")
    assert result.ok is False and result.absent is False
    assert "the governed read failed" in result.reason


def test_absence_is_declared_per_tool_never_inferred():
    result, _ = _acquire(_log_tool(absent_when=None), GONE)
    assert result.absent is False and "the governed read failed" in result.reason


def test_absent_when_must_be_a_compiled_pattern():
    with pytest.raises(ContractViolation, match="compiled pattern"):
        _log_tool(absent_when="not found")
    assert _log_tool(absent_when=re.compile("x")).absent_when.pattern == "x"


def test_both_catalog_log_tools_declare_the_connector_pattern():
    from backend.api.investigation_catalog import InvestigationWindow, ToolComposition, investigation_tools

    now = datetime.now(timezone.utc)
    tools = {t.key: t for t in investigation_tools(ToolComposition(
        subject_ref=POD, window=InvestigationWindow(incident_start=now, now=now)))}
    assert tools["k8s.pod_logs"].absent_when is _LOG_UNAVAILABLE
    assert tools["k8s.pod_logs_previous"].absent_when is _LOG_UNAVAILABLE
    assert tools["k8s.pod_state"].absent_when is None
