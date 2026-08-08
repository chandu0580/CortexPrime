"""BC-8 Connectivity — the Capability Fabric.

One of the Constitution's nine bounded contexts, built here for the first time.
It owns the answer to *what executable abilities exist, who answers for them, and
may they run* — deliberately not *which one should serve this request*, which is
resolution and needs a request to resolve against.

Capability identity is structured text (``platform.github.pull_request.create``)
rather than a ULID, because it names an ability rather than an occurrence and has
to survive the implementation being rewritten.

This context imports ``contracts/`` and ``platform/`` and nothing else.
See ADR-032.
"""

from backend.contexts.connectivity.application import *  # noqa: F401,F403
from backend.contexts.connectivity.application import __all__ as _application_all
from backend.contexts.connectivity.domain import *  # noqa: F401,F403
from backend.contexts.connectivity.domain import __all__ as _domain_all
from backend.contexts.connectivity.infrastructure import *  # noqa: F401,F403
from backend.contexts.connectivity.infrastructure import __all__ as _infrastructure_all

__all__ = list(_domain_all) + list(_application_all) + list(_infrastructure_all)
