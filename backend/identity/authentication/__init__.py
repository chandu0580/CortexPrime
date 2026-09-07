"""Authentication primitives — Phase 10.14 (ADR-107).

What was removed
----------------
``providers.py`` held ``DefaultAuthenticationProvider``, ``DefaultTokenProvider``
and ``DefaultIdentityProvider``. None was ever registered:
``register_identity_services()`` wires nine services and none of them is one of
these three, nor the ``UserRepository`` they depended on.

They mattered anyway, because **this file re-exported them**. Importing any
submodule of a package executes its ``__init__``, so
``backend/main.py -> identity.di -> password_verifier`` pulled ``providers`` in
at V1 boot, and with it ``repositories.iam`` and three ORM models that landed
on ``Base.metadata`` -- where ``init_db()``'s ``create_all`` would have created
the tables.

That is why Phase 10.13 refused to delete the module and this phase could:
"never called" and "not imported" are different questions, and a re-export
answers the second one differently from the first.

``PasswordVerifier`` stays. It is registered, it is used, and it never touched
the IAM tables.
"""

from backend.identity.authentication.password_verifier import PasswordVerifier
from backend.identity.interfaces.authentication import Identity, TokenClaims, TokenResult

__all__ = [
    "Identity", "TokenResult", "TokenClaims",
    "PasswordVerifier",
]
