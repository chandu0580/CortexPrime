"""Provider-specific connector knowledge. One module per provider, and no more.

What may live here
--------------------
A provider's ``OperationCatalog`` — the operations CortexPrime declares it can
perform, their shapes, their effect classes and what a valid answer looks like —
and a ``ProviderResponseTranslator`` for the places that provider's API departs
from convention.

What may not
--------------
An HTTP client, a retry loop, a credential lookup, a session, a pagination
walker, a cache, or any code that decides whether an action is permitted. Each
of those belongs to a layer that already exists: transport, Execution, the
credential fabric, and the invocation gateway respectively.

The test for a new file here: it should be *data plus a small translator*. If it
needs a socket, it is in the wrong package.
"""

from backend.contexts.execution.infrastructure.adapters.connectors.github import (
    GITHUB_API_BASE,
    GITHUB_PROVIDER,
    GITHUB_PROVIDER_ID,
    GITHUB_SCOPES,
    GitHubResponseTranslator,
    build_github_channel,
    github_catalog,
)

__all__ = [
    "GITHUB_PROVIDER",
    "GITHUB_PROVIDER_ID",
    "GITHUB_API_BASE",
    "GITHUB_SCOPES",
    "GitHubResponseTranslator",
    "github_catalog",
    "build_github_channel",
]
