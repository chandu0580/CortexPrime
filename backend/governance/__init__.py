# Phase 10.22 (ADR-116): policy_engine.py is a gitignored v2.0 component ("not part
# of v1.0.0 GA"). Re-exporting it here made every importer of this package --
# including the mission and execution services -- fail on a clean checkout.
from backend.governance.service import GovernanceService

__all__ = ["GovernanceService"]
