from __future__ import annotations

from backend.core.dependency_container import container
from backend.database.repositories.factory import repo_factory
from backend.identity.audit.audit_hooks import IdentityAuditHooks
from backend.identity.authentication.password_verifier import PasswordVerifier
from backend.identity.authorization.abac import ABACEvaluator
from backend.identity.authorization.permission_evaluator import DefaultPermissionEvaluator
from backend.identity.authorization.rbac import RBACProvider
from backend.identity.health import IdentityHealth
from backend.identity.jwt.access_token import AccessTokenProvider
from backend.identity.jwt.key_store import InMemoryKeyStore
from backend.identity.jwt.refresh_token import RefreshTokenProvider
from backend.identity.session.session_runtime import SessionRuntime


def register_identity_services() -> None:
    key_store = InMemoryKeyStore()
    container.register("identity_key_store", key_store)

    access_token_provider = AccessTokenProvider(key_store)
    container.register("identity_access_token_provider", access_token_provider)

    refresh_token_provider = RefreshTokenProvider(key_store)
    container.register("identity_refresh_token_provider", refresh_token_provider)

    password_verifier = PasswordVerifier()
    container.register("identity_password_verifier", password_verifier)

    session_runtime = SessionRuntime()
    container.register("identity_session_runtime", session_runtime)

    audit_hooks = IdentityAuditHooks()
    container.register("identity_audit_hooks", audit_hooks)

    rbac_provider = RBACProvider()
    container.register("identity_rbac_provider", rbac_provider)

    abac_evaluator = ABACEvaluator()
    container.register("identity_abac_evaluator", abac_evaluator)

    permission_evaluator = DefaultPermissionEvaluator(rbac_provider, abac_evaluator)
    container.register("identity_permission_evaluator", permission_evaluator)

    health = IdentityHealth(key_store, session_runtime)
    container.register("identity_health", health)

    container.register("identity_repo_factory", repo_factory)

    _warn_if_unset()
    _log_registration()


def _warn_if_unset() -> None:
    import os
    if not os.getenv("JWT_SECRET_KEY"):
        import logging
        logging.getLogger(__name__).warning(
            "JWT_SECRET_KEY not set — using ephemeral key. "
            "Tokens will invalidate on restart. Set JWT_SECRET_KEY in .env"
        )


def _log_registration() -> None:
    import logging
    log = logging.getLogger(__name__)
    log.info("Identity Runtime services registered: key_store, token_providers, auth_providers, session_runtime, rbac, abac, audit_hooks, health")
