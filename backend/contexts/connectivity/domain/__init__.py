"""Capability Fabric domain: identity, contract, lifecycle, trust."""

from backend.contexts.connectivity.domain.authorization import *  # noqa: F401,F403
from backend.contexts.connectivity.domain.binding import *  # noqa: F401,F403
from backend.contexts.connectivity.domain.binding import __all__ as _binding_all
from backend.contexts.connectivity.domain.resolution import *  # noqa: F401,F403
from backend.contexts.connectivity.domain.resolution import __all__ as _resolution_all
from backend.contexts.connectivity.domain.authorization import __all__ as _authz_all
from backend.contexts.connectivity.domain.budgets import *  # noqa: F401,F403
from backend.contexts.connectivity.domain.budgets import __all__ as _budgets_all
from backend.contexts.connectivity.domain.candidate import *  # noqa: F401,F403
from backend.contexts.connectivity.domain.candidate import __all__ as _candidate_all
from backend.contexts.connectivity.domain.discovery import *  # noqa: F401,F403
from backend.contexts.connectivity.domain.discovery import __all__ as _discovery_all
from backend.contexts.connectivity.domain.endpoint import *  # noqa: F401,F403
from backend.contexts.connectivity.domain.endpoint import __all__ as _endpoint_all
from backend.contexts.connectivity.domain.contract import *  # noqa: F401,F403
from backend.contexts.connectivity.domain.contract import __all__ as _contract_all
from backend.contexts.connectivity.domain.definition import *  # noqa: F401,F403
from backend.contexts.connectivity.domain.definition import __all__ as _definition_all
from backend.contexts.connectivity.domain.errors import *  # noqa: F401,F403
from backend.contexts.connectivity.domain.errors import __all__ as _errors_all
from backend.contexts.connectivity.domain.events import *  # noqa: F401,F403
from backend.contexts.connectivity.domain.events import __all__ as _events_all
from backend.contexts.connectivity.domain.identifiers import *  # noqa: F401,F403
from backend.contexts.connectivity.domain.identifiers import __all__ as _id_all
from backend.contexts.connectivity.domain.lifecycle import *  # noqa: F401,F403
from backend.contexts.connectivity.domain.lifecycle import __all__ as _lifecycle_all

__all__ = (
    list(_authz_all)
    + list(_binding_all)
    + list(_resolution_all)
    + list(_budgets_all)
    + list(_candidate_all)
    + list(_discovery_all)
    + list(_endpoint_all)
    + list(_id_all)
    + list(_lifecycle_all)
    + list(_contract_all)
    + list(_definition_all)
    + list(_errors_all)
    + list(_events_all)
)
