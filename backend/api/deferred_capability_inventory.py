"""What Phase 5.3 found, considered, and deliberately did not build.

Why this is a module and not a paragraph in the ADR
-----------------------------------------------------
A deferral written only in prose becomes a deferral nobody can find. This is
structured so a test can assert it — specifically, that nothing on the deferred
list has quietly acquired an implementation between now and whenever somebody
next looks. ``assert_deferrals_intact`` is that check.

The three entries here were named by the Phase 5.3 directive as things to
inventory rather than implement. Each says what exists today, what the
consequence of the gap is, and what building it would actually require — because
"deferred" without those three is indistinguishable from "forgotten".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

__all__ = [
    "Disposition",
    "DeferredCapability",
    "DEFERRED_CAPABILITIES",
    "assert_deferrals_intact",
]


class Disposition(str, Enum):
    """What was decided about a capability that was found but not built."""

    DEFERRED = "deferred"
    """Considered, scoped, and not built in this phase. Has a named owner phase."""

    REFUSED_BY_DEFAULT = "refused_by_default"
    """Reachable in code but fails closed until a deployment opts in."""

    ABSENT = "absent"
    """Not present at all. Absence is the current behaviour, and it is safe."""


@dataclass(frozen=True)
class DeferredCapability:
    """One thing that exists in the problem space and not in the code."""

    name: str
    disposition: Disposition
    current_behaviour: str
    consequence: str
    what_it_would_take: str
    proposed_phase: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "disposition": self.disposition.value,
            "current_behaviour": self.current_behaviour,
            "consequence": self.consequence,
            "what_it_would_take": self.what_it_would_take,
            "proposed_phase": self.proposed_phase,
        }


DEFERRED_CAPABILITIES = (
    DeferredCapability(
        name="MCP over SSE",
        disposition=Disposition.ABSENT,
        current_behaviour=(
            "``TransportKind.MCP_SSE`` exists as vocabulary and ``McpSession`` "
            "models initialization state, but no SSE reader does. The kind is "
            "**absent from ``PRODUCTION_TRANSPORT_KINDS``**, so "
            "``HttpxTransportAdapter`` refuses it outright rather than "
            "attempting a request/response call against a stream."
        ),
        consequence=(
            "SSE-only MCP servers are unusable. Nothing degrades and nothing "
            "half-connects: the absence is a clean refusal."
        ),
        what_it_would_take=(
            "A streaming reader with its own idle-timeout and per-frame "
            "accounting -- ``TransportPolicy`` already names a per-frame ceiling "
            "for exactly this -- plus a ``TransportOutcome`` shape that can "
            "express a stream rather than one response body. That is a contract "
            "change, not an adapter, which is precisely why it is not a Phase "
            "5.3 edit."
        ),
        proposed_phase="5.4",
    ),
    DeferredCapability(
        name="Sandboxed stdio MCP workers",
        disposition=Disposition.ABSENT,
        current_behaviour=(
            "No worker launches a subprocess. ``IsolationTier`` names "
            "``CONTAINED`` and ``SEALED``, and no implementation claims either, "
            "so worker selection refuses every operation whose effect class "
            "needs more than ``AMBIENT`` -- which is why the GitHub catalog's "
            "two irreversible writes are still refused."
        ),
        consequence=(
            "Irreversible writes cannot be performed by any worker in this "
            "platform. That is the current, honest state, and it is the reason "
            "the first governed operation is a read."
        ),
        what_it_would_take=(
            "A process supervisor with a real resource boundary -- namespace or "
            "container isolation, a filesystem view, a network policy, a memory "
            "and CPU ceiling, and a kill path that works when the child ignores "
            "SIGTERM. Claiming ``CONTAINED`` on a bare ``subprocess.Popen`` "
            "would be the single most dangerous lie available here: it would "
            "unlock the write refusals without providing the containment they "
            "were refused for."
        ),
        proposed_phase="5.4",
    ),
    DeferredCapability(
        name="Tenant fairness in the durable queue",
        disposition=Disposition.ABSENT,
        current_behaviour=(
            "``SqlExecutionQueue.claim_batch`` orders by priority, then "
            "``available_at``, then ``sequence``. It is fair between items and "
            "silent about tenants: one tenant enqueuing ten thousand nodes is "
            "served before another tenant's single node that arrived later."
        ),
        consequence=(
            "A noisy tenant can starve a quiet one. ``tenant_depths()`` exists "
            "and makes the starvation observable, which is the honest half of "
            "the problem; nothing acts on it."
        ),
        what_it_would_take=(
            "A scheduling policy -- weighted fair queuing, per-tenant "
            "concurrency ceilings, or a deficit round robin -- plus the "
            "decision about what fairness means commercially, which is a "
            "product question and not one to settle inside a claim query. "
            "Adding an ORDER BY here without that decision would be inventing "
            "a policy in the persistence layer."
        ),
        proposed_phase="5.4",
    ),
)


def assert_deferrals_intact() -> tuple:
    """Confirm nothing on the deferred list has quietly grown an implementation.

    Checks the specific, cheap, structural signals -- a transport that claims
    SSE, a worker implementation that claims containment it cannot provide, a
    tenant clause in the queue claim. Returns the names it verified.

    It is not a proof of absence and does not claim to be. What it catches is
    the realistic failure: somebody adds one of these to make something work,
    the ADR still says "deferred", and the two disagree for months.
    """
    import inspect

    problems: list = []

    # MCP over SSE. The signal is not whether the *kind* is named -- it is
    # vocabulary and has been since Phase 4.2 -- but whether the production
    # transport adapter will carry it.
    from backend.contracts.transport import TransportKind
    from backend.platform.transport.httpx_adapter import PRODUCTION_TRANSPORT_KINDS

    if TransportKind.MCP_SSE in PRODUCTION_TRANSPORT_KINDS:
        problems.append(
            "MCP_SSE is now a production transport kind; SSE is recorded as "
            "unimplemented"
        )
    if TransportKind.MCP_STDIO in PRODUCTION_TRANSPORT_KINDS:
        problems.append(
            "MCP_STDIO is now a production transport kind; stdio is recorded as "
            "unimplemented and it is not a network transport at all"
        )

    # Sandboxed workers. The signal is a worker implementation claiming an
    # isolation tier stronger than the process it actually runs in.
    from backend.api.capability_execution_composition import build_github_connector

    source = inspect.getsource(build_github_connector)
    if "IsolationTier.CONTAINED" in source or "IsolationTier.SEALED" in source:
        problems.append(
            "the in-process connector now claims contained or sealed isolation; "
            "sandboxed execution is recorded as unimplemented, and claiming the "
            "tier would unlock the irreversible-write refusals without providing "
            "the containment they were refused for"
        )

    from backend.contexts.execution.infrastructure.sql_queue import SqlExecutionQueue

    claim = inspect.getsource(SqlExecutionQueue.claim_batch)
    if "tenant" in claim and "order_by" in claim.lower():
        # Cheap and specific: the ordering clause naming a tenant is what a
        # fairness policy would look like.
        ordering = claim[claim.lower().index("order_by"):]
        if "tenant" in ordering[:400]:
            problems.append(
                "the queue claim now orders by tenant; tenant fairness is "
                "recorded as absent"
            )

    if problems:
        raise AssertionError(
            "the deferred-capability inventory disagrees with the code: "
            + "; ".join(problems)
        )
    return tuple(entry.name for entry in DEFERRED_CAPABILITIES)
