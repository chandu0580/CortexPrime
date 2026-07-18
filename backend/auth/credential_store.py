"""
Encrypted credential storage using Fernet symmetric encryption.
Stores connector/service credentials encrypted at rest in JSON files.
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


class CredentialStore:
    """Encrypted credential store using Fernet symmetric encryption."""

    def __init__(self, storage_dir: str = "data/credentials"):
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


# Singleton
_credential_store: Optional[CredentialStore] = None


def get_credential_store() -> CredentialStore:
    global _credential_store
    if _credential_store is None:
        _credential_store = CredentialStore()
    return _credential_store
