from __future__ import annotations

import secrets
from typing import Optional

import bcrypt


class PasswordVerifier:
    def __init__(self, pepper: Optional[str] = None):
        self._pepper = pepper or ""

    def hash_password(self, password: str) -> str:
        salted = password + self._pepper
        return bcrypt.hashpw(salted.encode(), bcrypt.gensalt()).decode()

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            salted = password + self._pepper
            return bcrypt.checkpw(salted.encode(), password_hash.encode())
        except Exception:
            return False

    def generate_temp_password(self, length: int = 24) -> str:
        return secrets.token_urlsafe(length)
