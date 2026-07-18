from __future__ import annotations

import logging
import os
from typing import Any, Optional

log = logging.getLogger(__name__)

try:
    import hvac
    _HVAC_AVAILABLE = True
except ImportError:
    _HVAC_AVAILABLE = False

_SECRET_MOUNT: str = "secret/data"


class VaultClient:
    def __init__(self) -> None:
        self._client: Optional[hvac.Client] = None
        self._available: bool = False

    async def connect(self) -> bool:
        if not _HVAC_AVAILABLE:
            log.warning("hvac not installed — Vault disabled")
            return False
        addr = os.getenv("VAULT_ADDR", "http://localhost:8200")
        token = os.getenv("VAULT_TOKEN", "")

        try:
            self._client = hvac.Client(url=addr, token=token)
            if not self._client.is_authenticated():
                log.warning("Vault authentication failed")
                self._available = False
                return False
            log.info("Vault connected and authenticated (%s)", addr)
            self._available = True
            return True
        except Exception as exc:
            log.warning("Vault connect failed: %s", exc)
            self._available = False
            return False

    # ------------------------------------------------------------------
    # Secrets (KV v2)
    # ------------------------------------------------------------------

    async def get_secret(self, path: str, key: Optional[str] = None) -> Optional[Any]:
        if not self._available or self._client is None:
            return None
        try:
            secret = self._client.secrets.kv.v2.read_secret_version(path=path, mount_point="secret")
            data = secret.get("data", {}).get("data", {})
            return data.get(key) if key else data
        except Exception as exc:
            log.error("Secret read failed for %s: %s", path, exc)
            return None

    async def set_secret(self, path: str, secrets: dict[str, Any]) -> bool:
        if not self._available or self._client is None:
            return False
        try:
            self._client.secrets.kv.v2.create_or_update_secret(path=path, secret=secrets, mount_point="secret")
            log.info("Secret written: %s", path)
            return True
        except Exception as exc:
            log.error("Secret write failed for %s: %s", path, exc)
            return False

    async def delete_secret(self, path: str) -> bool:
        if not self._available or self._client is None:
            return False
        try:
            self._client.secrets.kv.v2.delete_metadata_and_all_versions(path=path, mount_point="secret")
            log.info("Secret deleted: %s", path)
            return True
        except Exception as exc:
            log.error("Secret delete failed for %s: %s", path, exc)
            return False

    async def list_secrets(self, path: str) -> list[str]:
        if not self._available or self._client is None:
            return []
        try:
            resp = self._client.secrets.kv.v2.list_secrets(path=path, mount_point="secret")
            return resp.get("data", {}).get("keys", [])
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Dynamic database credentials
    # ------------------------------------------------------------------

    async def get_db_credentials(self, role_name: str, mount_point: str = "database") -> Optional[dict[str, Any]]:
        if not self._available or self._client is None:
            return None
        try:
            creds = self._client.secrets.database.generate_credentials(role_name, mount_point=mount_point)
            return creds.get("data", {})
        except Exception as exc:
            log.error("DB credentials generation failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        self._client = None
        self._available = False
        log.info("Vault client closed")

    @property
    def is_available(self) -> bool:
        return self._available


vault_client = VaultClient()
