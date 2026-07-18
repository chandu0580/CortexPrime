from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urlencode

import httpx

from backend.identity.providers.base import OAuthProvider, OAuthUserInfo

log = logging.getLogger(__name__)


class GoogleProvider(OAuthProvider):
    @property
    def name(self) -> str:
        return "google"

    def _get_config(self) -> dict[str, str]:
        return {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "scopes": os.getenv("GOOGLE_SCOPES", "openid email profile"),
        }

    async def get_auth_url(self, redirect_uri: str, state: str) -> str:
        cfg = self._get_config()
        params = urlencode({
            "client_id": cfg["client_id"],
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": cfg["scopes"],
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        })
        return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"

    async def exchange_code(self, code: str, redirect_uri: str) -> str:
        cfg = self._get_config()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
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
                "https://www.googleapis.com/oauth2/v3/userinfo",
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
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
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
