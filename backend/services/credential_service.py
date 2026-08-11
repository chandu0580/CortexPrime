"""In-process credential store for V1 connectors. **No environment fallback.**

Phase 5.15 (ADR-058) removed the ambient path this module used to carry:
``load()`` fell back to ``os.getenv`` per connector type, which meant any code
that constructed a connector silently consumed whatever provider credentials
the process environment happened to hold — demonstrated in Phase 5.14, when
merely booting the application contacted GitHub.

Now the store answers only with what somebody explicitly put in it. The one
sanctioned way environment configuration gets here is
``backend.api.connector_credential_composition.bootstrap_connector_credentials``
— a single, logged composition act in the application lifespan. A process that
never performs it gets empty credentials and visibly degraded connectors, not
a quiet borrow from ``.env``.
"""

import logging
from typing import Dict

log = logging.getLogger(__name__)

# Keep in-memory store
_CREDENTIAL_STORE: Dict[str, dict] = {}


class CredentialService:
    @classmethod
    def store(cls, connector_type: str, credentials: dict) -> None:
        """Stores credentials for a connector type."""
        log.info(f"Storing credentials for {connector_type}")
        _CREDENTIAL_STORE[connector_type] = dict(credentials)

    @classmethod
    def load(cls, connector_type: str) -> dict:
        """Loads stored credentials. Empty if nothing was explicitly stored.

        Deliberately no environment fallback: what the store was never given,
        it does not have. See the module docstring.
        """
        if connector_type in _CREDENTIAL_STORE:
            return dict(_CREDENTIAL_STORE[connector_type])
        return {}

    @classmethod
    def exists(cls, connector_type: str) -> bool:
        """Whether any credentials were explicitly stored for this type."""
        return connector_type in _CREDENTIAL_STORE and any(
            _CREDENTIAL_STORE[connector_type].values()
        )

    @classmethod
    def remove(cls, connector_type: str) -> None:
        """Removes credentials from the store."""
        if connector_type in _CREDENTIAL_STORE:
            del _CREDENTIAL_STORE[connector_type]
