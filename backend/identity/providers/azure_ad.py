from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urlencode

import httpx

from backend.identity.providers.base import OAuthProvider, OAuthUserInfo

log = logging.getLogger(__name__)


class AzureADProvider(OAuthProvider):
    @property
    def name(self) -> str:
        return "azure_ad"

    def _get_config(self) -> dict[str, str]:
        return {
            "client_id": os.getenv("AZURE_CLIENT_ID", ""),
            "client_secret": os.getenv("AZURE_CLIENT_SECRET", ""),
            "tenant": os.getenv("AZURE_TENANT_ID", "common"),
            "scopes": os.getenv("AZURE_SCOPES", "openid email profile"),
        }

    async def get_auth_url(self, redirect_uri: str, state: str) -> str:
        cfg = self._get_config()
        tenant = cfg["tenant"]
        params = urlencode({
            "client_id": cfg["client_id"],
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "response_mode": "query",
            "scope": cfg["scopes"],
            "state": state,
        })
        return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?{params}"

    async def exchange_code(self, code: str, redirect_uri: str) -> str:
        cfg = self._get_config()
        tenant = cfg["tenant"]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                data={
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("access_token", "")

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return OAuthUserInfo(
                sub=data.get("id", ""),
                email=data.get("mail", data.get("userPrincipalName", "")),
                display_name=data.get("displayName", ""),
                provider=self.name,
                raw=data,
            )

    async def refresh_token(self, refresh_token: str) -> str:
        cfg = self._get_config()
        tenant = cfg["tenant"]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                data={
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("access_token", "")
