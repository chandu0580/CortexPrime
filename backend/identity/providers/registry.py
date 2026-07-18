from __future__ import annotations

import logging
from typing import Optional

from backend.identity.providers.base import OAuthProvider

log = logging.getLogger(__name__)


class IdentityProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, OAuthProvider] = {}

    def register(self, provider: OAuthProvider) -> None:
        self._providers[provider.name] = provider
        log.info("OAuth provider registered: %s", provider.name)

    def get(self, name: str) -> Optional[OAuthProvider]:
        return self._providers.get(name)

    def list(self) -> list[str]:
        return list(self._providers.keys())

    def is_supported(self, name: str) -> bool:
        return name in self._providers


_registry: Optional[IdentityProviderRegistry] = None


def get_provider_registry() -> IdentityProviderRegistry:
    global _registry
    if _registry is None:
        _registry = IdentityProviderRegistry()
    return _registry


def register_default_providers() -> None:
    import os
    registry = get_provider_registry()

    from backend.identity.providers.azure_ad import AzureADProvider
    from backend.identity.providers.google import GoogleProvider
    from backend.identity.providers.okta import OktaProvider
    from backend.identity.providers.keycloak import KeycloakProvider

    azure_client_id = os.getenv("AZURE_CLIENT_ID", "")
    if azure_client_id:
        registry.register(AzureADProvider())

    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if google_client_id:
        registry.register(GoogleProvider())

    okta_domain = os.getenv("OKTA_DOMAIN", "")
    if okta_domain:
        registry.register(OktaProvider())

    keycloak_url = os.getenv("KEYCLOAK_URL", "")
    if keycloak_url:
        registry.register(KeycloakProvider())

    log.info("Identity providers registered: %s", registry.list())
