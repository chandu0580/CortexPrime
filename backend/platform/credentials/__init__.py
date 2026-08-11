"""The credential and secret fabric (Phase 4.1).

Where it sits
---------------
``platform/`` rather than a bounded context, deliberately. Credentials are needed
by Execution (which decides *when* one is required) and described by Connectivity
(which decides *what provider* is being reached), and those two may not import
each other. A new bounded context was the alternative and was rejected: the
fabric owns no business decision, only a mechanism, and Phase 4.1's stop
condition names a new bounded context as a reason to report rather than build.

The one rule
--------------
**A reference may be written down. Material may not.**

    CredentialRef       opaque, tenant-qualified, safe in records and audit
    CredentialGrant     metadata about an issued credential -- safe to persist
    CredentialMaterial  the secret -- runtime-only, unserialisable, one exit

Everything else follows from keeping those apart.

Possession is not authority
-----------------------------
A credential authenticates to a provider. It does not authorize a CortexPrime
action — the invocation gateway already did that, and obtaining a credential does
not revisit it. A leaked credential therefore still fails at the gate, which is
the property that makes the whole arrangement worth having.

    contracts/credential.py   the published vocabulary (ref, type, state, scope)
    material                  the secret, and everything stopping it escaping
    request                   the request, the grant, and every refusal reason
    broker                    the one issuer; fail-closed, no fallback
    development               a non-production adapter that refuses production
    redaction                 the last line, for text the type system cannot reach
"""

from backend.platform.credentials.broker import (
    CREDENTIAL_METRICS,
    AuthorityRevalidator,
    CredentialAdapter,
    CredentialBroker,
    IssuedCredential,
)
from backend.platform.credentials.development import DevelopmentCredentialProvider
from backend.platform.credentials.material import REDACTED, CredentialMaterial
from backend.platform.credentials.redaction import (
    NON_SENSITIVE_KEYS,
    SENSITIVE_KEY_FRAGMENTS,
    is_sensitive_key,
    redact_mapping,
    safe_exception_text,
    scrub_text,
)
from backend.platform.credentials.request import (
    MAX_CREDENTIAL_LIFETIME_SECONDS,
    CredentialGrant,
    CredentialRefusal,
    CredentialRefused,
    CredentialRequest,
)

__all__ = [
    "CredentialBroker",
    "CredentialAdapter",
    "AuthorityRevalidator",
    "IssuedCredential",
    "CredentialMaterial",
    "REDACTED",
    "CredentialRequest",
    "CredentialGrant",
    "CredentialRefusal",
    "CredentialRefused",
    "MAX_CREDENTIAL_LIFETIME_SECONDS",
    "CREDENTIAL_METRICS",
    "DevelopmentCredentialProvider",
    "redact_mapping",
    "scrub_text",
    "safe_exception_text",
    "is_sensitive_key",
    "SENSITIVE_KEY_FRAGMENTS",
    "NON_SENSITIVE_KEYS",
]
