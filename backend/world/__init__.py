"""The World Plane — CortexPrime's epistemic substrate.

What it is: the durable record of what CortexPrime knows about external systems,
built from provenanced observations. What it is not: an execution authority. The
World Plane describes reality; it never acts on it (ADR-062). Knowledge informs
action only through Intelligence → Harness → Governance → Execution, never
directly.

Phase 7.2 builds the first ledger: observation ingestion. Facts, beliefs,
hypotheses, predictions, contradiction resolution, and world queries are later
phases and are deliberately absent here.

Layering (enforced by BND-WORLD-CANNOT-EXECUTE):
  application/    ports + the ingestion service — contracts + the secret
                  detector only; no database, no connectors, no execution.
  infrastructure/ the durable SQL repository — the one place that touches the
                  durable store.
"""
