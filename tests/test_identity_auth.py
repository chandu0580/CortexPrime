"""Identity authentication — Phase 10.14 (ADR-107).

The three provider test classes that stood here were removed together with the
module they covered. ``DefaultAuthenticationProvider``, ``DefaultTokenProvider``
and ``DefaultIdentityProvider`` had no production consumer: nothing registered
them, and their only effect at runtime was a package re-export that dragged the
dead IAM repository into V1 boot -- and with it three ORM models that
``init_db()`` would have created tables for.

``PasswordVerifier`` is the part that stays. It is registered by
``register_identity_services()``, it is used, and it never touched the IAM
tables -- so its tests stay with it.
"""

from __future__ import annotations

import pytest

from backend.identity.authentication.password_verifier import PasswordVerifier


@pytest.fixture
def password_verifier():
    return PasswordVerifier()


class TestPasswordVerifier:
    def test_hash_and_verify(self, password_verifier):
        pw_hash = password_verifier.hash_password("SecureP@ss123")
        assert password_verifier.verify_password("SecureP@ss123", pw_hash) is True
        assert password_verifier.verify_password("WrongPassword", pw_hash) is False

    def test_generate_temp_password(self, password_verifier):
        temp = password_verifier.generate_temp_password()
        assert len(temp) == 32
        assert isinstance(temp, str)
