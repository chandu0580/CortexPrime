from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from backend.security_center.models import (
    AuthProvider,
    SecretProvider,
    SecretReference,
)

log = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    provider: AuthProvider
    client_id: str
    client_secret: str
    authorization_url: str = ""
    token_url: str = ""
    userinfo_url: str = ""
    metadata_url: str = ""
    issuer: str = ""
    scopes: List[str] = field(default_factory=lambda: ["openid", "profile", "email"])
    redirect_uri: str = ""
    jwks_uri: str = ""
    certificate: str = ""


@dataclass
class AuthProviderResult:
    success: bool
    provider: AuthProvider
    user_id: str = ""
    email: str = ""
    display_name: str = ""
    roles: List[str] = field(default_factory=list)
    attributes: Dict[str, str] = field(default_factory=dict)
    access_token: str = ""
    id_token: str = ""
    error: str = ""


class AuthProviderManager:
    """
    Multi-provider authentication support.

    Supports OAuth 2.0, OpenID Connect (OIDC), and SAML 2.0.
    Each provider is configured via environment variables.
    Secrets can be sourced from environment variables or external secret providers.
    """

    def __init__(self) -> None:
        self._providers: Dict[AuthProvider, ProviderConfig] = {}
        self._init_providers()

    def _init_providers(self) -> None:
        if os.getenv("OAUTH2_CLIENT_ID"):
            self._providers[AuthProvider.OAUTH2] = ProviderConfig(
                provider=AuthProvider.OAUTH2,
                client_id=os.getenv("OAUTH2_CLIENT_ID", ""),
                client_secret=os.getenv("OAUTH2_CLIENT_SECRET", ""),
                authorization_url=os.getenv("OAUTH2_AUTH_URL", ""),
                token_url=os.getenv("OAUTH2_TOKEN_URL", ""),
                redirect_uri=os.getenv("OAUTH2_REDIRECT_URI", ""),
                scopes=os.getenv("OAUTH2_SCOPES", "openid profile email").split(),
            )
            log.info("OAuth 2.0 provider configured: %s", os.getenv("OAUTH2_CLIENT_ID", "")[:12])

        if os.getenv("OIDC_CLIENT_ID"):
            self._providers[AuthProvider.OIDC] = ProviderConfig(
                provider=AuthProvider.OIDC,
                client_id=os.getenv("OIDC_CLIENT_ID", ""),
                client_secret=os.getenv("OIDC_CLIENT_SECRET", ""),
                metadata_url=os.getenv("OIDC_METADATA_URL", ""),
                issuer=os.getenv("OIDC_ISSUER", ""),
                jwks_uri=os.getenv("OIDC_JWKS_URI", ""),
                redirect_uri=os.getenv("OIDC_REDIRECT_URI", ""),
                scopes=os.getenv("OIDC_SCOPES", "openid profile email").split(),
            )
            log.info("OpenID Connect provider configured: %s", os.getenv("OIDC_CLIENT_ID", "")[:12])

        if os.getenv("SAML_ENTITY_ID"):
            self._providers[AuthProvider.SAML] = ProviderConfig(
                provider=AuthProvider.SAML,
                client_id=os.getenv("SAML_ENTITY_ID", ""),
                client_secret="",
                authorization_url=os.getenv("SAML_SSO_URL", ""),
                certificate=os.getenv("SAML_CERTIFICATE", ""),
                redirect_uri=os.getenv("SAML_ACS_URL", ""),
            )
            log.info("SAML 2.0 provider configured: %s", os.getenv("SAML_ENTITY_ID", "")[:30])

    # ------------------------------------------------------------------
    # Provider status
    # ------------------------------------------------------------------

    def is_configured(self, provider: AuthProvider) -> bool:
        return provider in self._providers

    def get_provider(self, provider: AuthProvider) -> Optional[ProviderConfig]:
        return self._providers.get(provider)

    def list_configured(self) -> List[Dict[str, Any]]:
        return [
            {"provider": p.value, "client_id": c.client_id[:12] + "..." if len(c.client_id) > 12 else c.client_id}
            for p, c in self._providers.items()
        ]

    # ------------------------------------------------------------------
    # OAuth 2.0 authorization URL
    # ------------------------------------------------------------------

    def get_oauth2_authorization_url(self, state: str) -> Optional[str]:
        cfg = self._providers.get(AuthProvider.OAUTH2)
        if cfg is None:
            return None
        params = {
            "response_type": "code",
            "client_id": cfg.client_id,
            "redirect_uri": cfg.redirect_uri,
            "scope": " ".join(cfg.scopes),
            "state": state,
        }
        return f"{cfg.authorization_url}?{urlencode(params)}"

    # ------------------------------------------------------------------
    # OAuth 2.0 token exchange
    # ------------------------------------------------------------------

    async def exchange_oauth2_code(self, code: str, redirect_uri: str) -> AuthProviderResult:
        cfg = self._providers.get(AuthProvider.OAUTH2)
        if cfg is None:
            return AuthProviderResult(success=False, provider=AuthProvider.OAUTH2, error="Provider not configured")

        try:
            import httpx
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": cfg.client_id,
                "client_secret": cfg.client_secret,
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(cfg.token_url, data=data, timeout=15)
                response.raise_for_status()
                token_data = response.json()

            id_token = token_data.get("id_token", "")
            access_token = token_data.get("access_token", "")

            user_info = await self._get_userinfo(access_token, cfg)

            return AuthProviderResult(
                success=True,
                provider=AuthProvider.OAUTH2,
                user_id=user_info.get("sub") or user_info.get("id", ""),
                email=user_info.get("email", ""),
                display_name=user_info.get("name", user_info.get("preferred_username", "")),
                roles=user_info.get("roles", user_info.get("groups", [])),
                attributes=user_info,
                access_token=access_token,
                id_token=id_token,
            )
        except Exception as exc:
            log.warning("OAuth2 token exchange failed: %s", exc)
            return AuthProviderResult(
                success=False, provider=AuthProvider.OAUTH2, error=str(exc)
            )

    # ------------------------------------------------------------------
    # OpenID Connect
    # ------------------------------------------------------------------

    def get_oidc_authorization_url(self, state: str) -> Optional[str]:
        cfg = self._providers.get(AuthProvider.OIDC)
        if cfg is None:
            return None
        auth_url = cfg.authorization_url
        if not auth_url and cfg.metadata_url:
            auth_url = f"{cfg.metadata_url.rstrip('/')}/authorize"
        if not auth_url:
            auth_url = os.getenv("OIDC_AUTH_URL", f"{cfg.issuer}/authorize")
        params = {
            "response_type": "code",
            "client_id": cfg.client_id,
            "redirect_uri": cfg.redirect_uri,
            "scope": " ".join(cfg.scopes),
            "state": state,
        }
        return f"{auth_url}?{urlencode(params)}"

    async def exchange_oidc_code(self, code: str, redirect_uri: str) -> AuthProviderResult:
        cfg = self._providers.get(AuthProvider.OIDC)
        if cfg is None:
            return AuthProviderResult(success=False, provider=AuthProvider.OIDC, error="Provider not configured")

        try:
            import httpx
            token_url = cfg.token_url
            if not token_url and cfg.metadata_url:
                token_url = f"{cfg.metadata_url.rstrip('/')}/token"
            if not token_url:
                token_url = os.getenv("OIDC_TOKEN_URL", f"{cfg.issuer}/token")

            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": cfg.client_id,
                "client_secret": cfg.client_secret,
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, data=data, timeout=15)
                response.raise_for_status()
                token_data = response.json()

            id_token = token_data.get("id_token", "")
            access_token = token_data.get("access_token", "")

            user_info = await self._get_userinfo(access_token, cfg)

            return AuthProviderResult(
                success=True,
                provider=AuthProvider.OIDC,
                user_id=user_info.get("sub", ""),
                email=user_info.get("email", ""),
                display_name=user_info.get("name", user_info.get("preferred_username", "")),
                roles=user_info.get("roles", []),
                attributes=user_info,
                access_token=access_token,
                id_token=id_token,
            )
        except Exception as exc:
            log.warning("OIDC token exchange failed: %s", exc)
            return AuthProviderResult(
                success=False, provider=AuthProvider.OIDC, error=str(exc)
            )

    # ------------------------------------------------------------------
    # SAML 2.0
    # ------------------------------------------------------------------

    def get_saml_login_url(self, relay_state: str = "") -> Optional[str]:
        cfg = self._providers.get(AuthProvider.SAML)
        if cfg is None:
            return None
        return cfg.authorization_url

    async def process_saml_response(self, saml_response: str) -> AuthProviderResult:
        cfg = self._providers.get(AuthProvider.SAML)
        if cfg is None:
            return AuthProviderResult(success=False, provider=AuthProvider.SAML, error="Provider not configured")

        try:
            import base64
            import zlib
            from xml.etree import ElementTree

            decoded = base64.b64decode(saml_response)
            try:
                decoded = zlib.decompress(decoded)
            except Exception:
                pass

            root = ElementTree.fromstring(decoded)
            ns = {
                "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
                "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
            }

            attr_map: Dict[str, str] = {}
            for attr_stmt in root.iter(f"{{{ns['saml']}}}AttributeStatement"):
                for attr in attr_stmt.iter(f"{{{ns['saml']}}}Attribute"):
                    name = attr.get("Name", "")
                    values = [v.text or "" for v in attr.iter(f"{{{ns['saml']}}}AttributeValue")]
                    if values:
                        attr_map[name] = values[0]

            name_id_el = root.find(".//saml:NameID", ns)
            user_id = name_id_el.text if name_id_el is not None else ""

            return AuthProviderResult(
                success=True,
                provider=AuthProvider.SAML,
                user_id=user_id or attr_map.get("user_id", ""),
                email=attr_map.get("email", attr_map.get("mail", "")),
                display_name=attr_map.get("displayName", attr_map.get("cn", user_id)),
                roles=[attr_map.get("role", attr_map.get("memberOf", ""))],
                attributes=attr_map,
            )
        except Exception as exc:
            log.warning("SAML response processing failed: %s", exc)
            return AuthProviderResult(
                success=False, provider=AuthProvider.SAML, error=str(exc)
            )

    # ------------------------------------------------------------------
    # Secrets management
    # ------------------------------------------------------------------

    async def resolve_secret_value(self, secret_ref: SecretReference) -> Optional[str]:
        provider_type = secret_ref.provider
        path = secret_ref.provider_path

        if provider_type == SecretProvider.ENV:
            return os.getenv(path)

        if provider_type == SecretProvider.HASHICORP_VAULT:
            return await self._vault_read(path)

        if provider_type == SecretProvider.AZURE_KEY_VAULT:
            return await self._azure_key_vault_read(path)

        if provider_type == SecretProvider.AWS_SECRETS_MANAGER:
            return await self._aws_secrets_manager_read(path)

        return None

    async def _vault_read(self, path: str) -> Optional[str]:
        try:
            import hvac
            vault_addr = os.getenv("VAULT_ADDR", "http://localhost:8200")
            vault_token = os.getenv("VAULT_TOKEN", "")
            client = hvac.Client(url=vault_addr, token=vault_token)
            if not client.is_authenticated():
                log.warning("Vault authentication failed")
                return None
            secret = client.secrets.kv.v2.read_secret_version(path=path)
            return json.dumps(secret.get("data", {}).get("data", {}))
        except Exception as exc:
            log.warning("Vault read failed for %s: %s", path, exc)
            return None

    async def _azure_key_vault_read(self, name: str) -> Optional[str]:
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
            vault_url = os.getenv("AZURE_KEY_VAULT_URL", "")
            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=vault_url, credential=credential)
            secret = client.get_secret(name)
            return secret.value
        except Exception as exc:
            log.warning("Azure Key Vault read failed for %s: %s", name, exc)
            return None

    async def _aws_secrets_manager_read(self, name: str) -> Optional[str]:
        try:
            import boto3
            from botocore.config import Config
            session = boto3.session.Session()
            client = session.client(
                "secretsmanager",
                config=Config(connect_timeout=5, read_timeout=10),
            )
            response = client.get_secret_value(SecretId=name)
            if "SecretString" in response:
                return response["SecretString"]
            return response.get("SecretBinary", b"").decode()
        except Exception as exc:
            log.warning("AWS Secrets Manager read failed for %s: %s", name, exc)
            return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _get_userinfo(self, access_token: str, cfg: ProviderConfig) -> Dict[str, Any]:
        if not cfg.userinfo_url and cfg.metadata_url:
            cfg.userinfo_url = f"{cfg.metadata_url.rstrip('/')}/userinfo"
        if not cfg.userinfo_url:
            return {}
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    cfg.userinfo_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception as exc:
            log.debug("Userinfo fetch failed: %s", exc)
        return {}

    def status(self) -> List[Dict[str, Any]]:
        return self.list_configured()


auth_providers = AuthProviderManager()
