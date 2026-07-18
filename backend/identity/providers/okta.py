from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urlencode

import httpx

from backend.identity.providers.base import OAuthProvider, OAuthUserInfo

log = logging.getLogger(__name__)


class OktaProvider(OAuthProvider):
    @property
    def name(self) -> str:
        return "okta"

    def _get_config(self) -> dict[str, str]:
        return {
            "client_id": os.getenv("OKTA_CLIENT_ID", ""),
            "client_secret": os.getenv("OKTA_CLIENT_SECRET", ""),
            "domain": os.getenv("OKTA_DOMAIN", ""),
            "scopes": os.getenv("OKTA_SCOPES", "openid email profile"),
        }

    async def get_auth_url(self, redirect_uri: str, state: str) -> str:
        cfg = self._get_config()
        domain = cfg["domain"]
        params = urlencode({
            "client_id": cfg["client_id"],
            "response_type": "code",
            "response_mode": "query",
            "redirect_uri": redirect_uri,
            "scope": cfg["scopes"],
            "state": state,
        })
        return f"https://{domain}/oauth2/default/v1/authorize?{params}"

    async def exchange_code(self, code: str, redirect_uri: str) -> str:
        cfg = self._get_config()
        domain = cfg["domain"]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://{domain}/oauth2/default/v1/token",
                data={
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("access_token", "")

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        cfg = self._get_config()
        domain = cfg["domain"]
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://{domain}/oauth2/default/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return OAuthUserInfo(
                sub=data.get("sub", ""),
                email=data.get("email", ""),
                display_name=data.get("name", ""),
                provider=self.name,
                raw=data,
            )

    async def refresh_token(self, refresh_token: str) -> str:
        cfg = self._get_config()
        domain = cfg["domain"]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://{domain}/oauth2/default/v1/token",
                data={
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("access_token", "")
