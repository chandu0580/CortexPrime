"""Phase 11.3 (ADR-123 D-20): model output can never crash an investigation.

Measured on the live cluster: glm-5.2 restated the seeded hypotheses with empty
references. The strict schema accepted the shape; the platform contract refused
the meaning while mapping; the raw ContractViolation escaped and crashed the
investigation, which then stayed ``investigating`` in the ledger forever."""
from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace

import pytest

from backend.api.investigation_catalog import PARTIAL_MODEL_OUTPUT, _merge_model_and_plan
from backend.contracts.errors import ContractViolation
from backend.intelligence.application.model_boundary import (
    GovernedModelProposalPort, InvestigationProposalSchema,
)
from backend.intelligence.application.proposal import ModelSchemaRejected

EMPTY_REF_OUTPUT = {
    "interpretation": "restating the differential",
    "hypotheses": [{"ref": "", "proposition": "required configuration is missing",
                    "subject_ref": "", "temporal_fit": "unknown"}],
    "tests": [],
}


class _Boundary:
    def __init__(self, schema):
        self._schema = schema

    async def propose(self, **_kwargs):
        return self._schema, SimpleNamespace(model_provider="openai-compatible")


def _context():
    return SimpleNamespace(context_digest="c" * 64, sections=(),
                           prompt_view=lambda: {"sections": []}, to_dict=lambda: {})


def test_model_content_that_breaks_a_contract_is_a_rejected_proposal_not_a_crash():
    schema = InvestigationProposalSchema.model_validate(EMPTY_REF_OUTPUT)
    port = GovernedModelProposalPort(boundary=_Boundary(schema), provider_label="test")
    investigation = SimpleNamespace(steps_taken=0, investigation_ref="winv_test", seq=4)
    with pytest.raises(ModelSchemaRejected, match="platform contract"):
        port.propose(context=_context(), investigation=investigation, now=None)


def test_the_merge_drops_unreferenced_hypotheses_says_so_and_keeps_valid_content():
    plan = {"interpretation": "plan", "tests": []}
    output = {"interpretation": "model", "tests": [], "hypotheses": [
        {"ref": "", "proposition": "unreferenced", "subject_ref": "s"},
        {"ref": "h-subjectless", "proposition": "no subject", "subject_ref": ""},
        {"ref": "h-network", "proposition": "the network is partitioned", "subject_ref": "s"}]}
    merged, note = _merge_model_and_plan(json.dumps(output), plan)
    assert [h["ref"] for h in merged["hypotheses"]] == ["h-network"]
    assert note and note.startswith(PARTIAL_MODEL_OUTPUT) and "2 model hypothesis" in note
    assert merged["interpretation"] == "model"
    clean, clean_note = _merge_model_and_plan(json.dumps({"interpretation": "m", "hypotheses": [], "tests": []}), plan)
    assert clean_note is None and clean["hypotheses"] == []
