"""The secret / context firewall (harness view).

The structured, field-aware secret detector moved to the platform layer in
Phase 7.2 (``backend.platform.credentials.inspection``) so the World Plane
ingestion boundary could reuse it without importing the harness. This module
re-exports it unchanged: the harness firewall is still the tripwire that
credentials never enter model context, model output, a trace, or a durable
spec — the primary control remains that credentials are minted at the last
gateway stage and never placed in any of those.
"""

from backend.platform.credentials.inspection import (
    SecretFinding,
    assert_no_secrets,
    find_secrets,
)

__all__ = ["SecretFinding", "find_secrets", "assert_no_secrets"]
