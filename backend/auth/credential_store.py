"""Encrypted credential storage. **Quarantined — not a production authority.**

What this is
--------------
A Fernet-encrypted, file-backed credential store predating the credential
fabric. It decrypts **every** stored credential into a process-wide dictionary
at construction (``_load_all``), keys them by a bare ``credential_id`` with no
tenant anywhere in the type, and is reached through a module-level
``get_credential_store()`` singleton.

That is the global credential dictionary and the ambient-tenant lookup the
Phase 4.1 fabric exists to make impossible — in one object.

Why it is still here
----------------------
It is **unreferenced**: no module in this repository imports it, verified by
search in Phase 4.1 and again in Phase 4.4. Deleting a credential store is a
decision with data attached to it — somebody's ``data/credentials/*.enc`` files
and their key — so it is quarantined rather than removed, and removing it is an
operator decision with its own review.

The guard below
-----------------
``allow_non_production=True`` must be passed explicitly to construct one, and
``get_credential_store()`` refuses outright. The point is not to make it
inconvenient; it is to make wiring it into a production path something a
reviewer cannot miss, because the previous state — a well-named, importable,
zero-friction credential store — is the state in which somebody uses it.

**There is one credential authority: ``CredentialProvider`` (ADR-040).** A
second one is not a fallback, it is a way for a credential to exist that nothing
in the authority chain issued.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet


def _get_or_create_key(key_path: Optional[Path] = None) -> bytes:
    """Get encryption key from file or environment, or create one."""
    env_key = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
    if env_key:
        return base64.urlsafe_b64decode(env_key.encode())

    if key_path is None:
        key_path = Path("data/credentials/.encryption_key")
    key_path.parent.mkdir(parents=True, exist_ok=True)

    if key_path.exists():
        return key_path.read_bytes()

    key = Fernet.generate_key()
    key_path.write_bytes(key)
    os.chmod(key_path, 0o600)  # owner read/write only
    return key


class LegacyCredentialStoreRefused(RuntimeError):
    """The quarantined V1 credential store was reached. Nothing was returned."""


class CredentialStore:
    """Encrypted V1 credential store. **Quarantined; see the module docstring.**"""

    def __init__(
        self,
        storage_dir: str = "data/credentials",
        *,
        allow_non_production: bool = False,
    ):
        if allow_non_production is not True:
            raise LegacyCredentialStoreRefused(
                "CredentialStore is a quarantined V1 credential authority and "
                "requires allow_non_production=True to be passed explicitly. It "
                "decrypts every stored credential into a process-wide dictionary "
                "with no tenant in the type. Provider credentials are issued by "
                "the credential fabric (ADR-040) against an authorized action; "
                "there is one credential authority and this is not it"
            )
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        key = _get_or_create_key(self._storage_dir / ".encryption_key")
        self._fernet = Fernet(key)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load_all()

    def _path_for(self, credential_id: str) -> Path:
        return self._storage_dir / f"{credential_id}.enc"

    def _load_all(self):
        for f in self._storage_dir.glob("*.enc"):
            cid = f.stem
            try:
                encrypted = f.read_bytes()
                decrypted = self._fernet.decrypt(encrypted)
                self._cache[cid] = json.loads(decrypted)
            except Exception:
                pass  # skip corrupted files

    def _save(self, credential_id: str):
        data = self._cache.get(credential_id)
        if data is None:
            return
        encrypted = self._fernet.encrypt(json.dumps(data).encode())
        self._path_for(credential_id).write_bytes(encrypted)

    def store(self, credential_id: str, credentials: Dict[str, Any]) -> str:
        self._cache[credential_id] = credentials
        self._save(credential_id)
        return credential_id

    def get(self, credential_id: str) -> Optional[Dict[str, Any]]:
        return self._cache.get(credential_id)

    def delete(self, credential_id: str) -> bool:
        if credential_id in self._cache:
            del self._cache[credential_id]
            path = self._path_for(credential_id)
            if path.exists():
                path.unlink()
            return True
        return False

    def list_ids(self) -> List[str]:
        return list(self._cache.keys())


def get_credential_store() -> CredentialStore:
    """**Removed as a usable accessor.** Always refuses.

    The module-level singleton it used to memoise is gone with it: a global that
    caches decrypted credentials is the exact shape the credential fabric was
    built to replace, and leaving it constructible-on-first-call meant a single
    import could bring one into existence for the life of the process.

    Nothing in this repository called this — verified by search — so removing
    the behaviour breaks no caller. It is kept as a refusing function rather
    than deleted so that a future call site fails loudly at the point of use,
    naming the authority it should have asked instead, rather than failing with
    an import error somebody resolves by rewriting the import.
    """
    raise LegacyCredentialStoreRefused(
        "get_credential_store() is withdrawn. Provider credentials are issued "
        "by CredentialProvider (ADR-040) against an authorized action, scoped "
        "to a tenant and bounded by the authority window. A process-wide store "
        "of decrypted credentials is not a fallback for that; it is a way for a "
        "credential to exist that nothing in the authority chain issued"
    )
