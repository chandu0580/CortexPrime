"""The secret / context firewall (Part F): structured, field-aware inspection
that credentials never entered a value bound for model context, model output,
a trace, an audit payload, replay state, or a durable execution spec.

Beyond substring grep
-----------------------
A `find_secrets` walk detects a secret three independent ways, so a leak has to
evade all three: by **key name** (a field whose name means "secret" — reusing
the platform's own `is_sensitive_key`, minus its documented non-sensitive
allowlist), by **value shape** (a string matching a known token pattern —
reusing the platform's `scrub_text` detectors), and by **type** (a
`CredentialMaterial` or any object advertising credential-ness). It recurses
dicts, lists, tuples, dataclasses, Pydantic models, and `__dict__`-bearing
objects, so a secret nested three levels down in a tool-argument object is
found at its path.

This is a *test and defense-in-depth* instrument, not the primary control. The
primary control is that credentials are minted at the last gateway stage and
never placed in a context, an output, or a span — the redaction on the trace
write path is the belt, and this is the tripwire that proves the belt holds.
"""

from __future__ import annotations

import base64
import dataclasses
from typing import Any, Iterator

from backend.platform.credentials.redaction import (
    NON_SENSITIVE_KEYS,
    _TEXT_PATTERNS,
    is_sensitive_key,
)

__all__ = ["SecretFinding", "find_secrets", "assert_no_secrets"]


@dataclasses.dataclass(frozen=True)
class SecretFinding:
    path: str
    why: str  # "key-name" | "value-shape" | "credential-type" | "encoded"


def _looks_like_secret_value(value: str) -> bool:
    return any(pattern.search(value) for pattern in _TEXT_PATTERNS)


def _is_credential_type(value: Any) -> bool:
    """A value that advertises itself as credential material. Names, not
    imports, so this stays dependency-light and catches look-alikes."""
    type_name = type(value).__name__.lower()
    if "credential" in type_name and "ref" not in type_name and "type" not in type_name:
        return True
    # CredentialMaterial renders ***redacted*** but is still a secret carrier.
    if type_name in {"credentialmaterial", "secretstr", "issuedcredential"}:
        return True
    return False


def _maybe_decode(value: str) -> str | None:
    """A base64 payload that decodes to something secret-shaped. Bounded so a
    large body cannot turn one check into a decode storm."""
    stripped = value.strip()
    if len(stripped) < 16 or len(stripped) > 4096:
        return None
    if any(c.isspace() for c in stripped):
        return None
    try:
        decoded = base64.b64decode(stripped, validate=True).decode("utf-8", "ignore")
    except Exception:
        return None
    return decoded or None


def _walk(value: Any, path: str, seen: set[int]) -> Iterator[SecretFinding]:
    if value is None or isinstance(value, (bool, int, float)):
        return
    ident = id(value)
    if ident in seen:
        return

    if _is_credential_type(value):
        yield SecretFinding(path or "<root>", "credential-type")
        return

    if isinstance(value, str):
        if _looks_like_secret_value(value):
            yield SecretFinding(path or "<root>", "value-shape")
            return
        decoded = _maybe_decode(value)
        if decoded is not None and _looks_like_secret_value(decoded):
            yield SecretFinding(path or "<root>", "encoded")
        return

    if isinstance(value, bytes):
        try:
            text = value.decode("utf-8", "ignore")
        except Exception:
            return
        if _looks_like_secret_value(text):
            yield SecretFinding(path or "<root>", "value-shape")
        return

    seen.add(ident)

    if isinstance(value, dict):
        for key, sub in value.items():
            key_str = str(key)
            child_path = f"{path}.{key_str}" if path else key_str
            # Key-name signal: a sensitive key that is not on the platform's
            # explicit non-sensitive allowlist, holding a non-empty value.
            if (
                is_sensitive_key(key_str)
                and key_str not in NON_SENSITIVE_KEYS
                and sub not in (None, "", [], {}, ())
            ):
                yield SecretFinding(child_path, "key-name")
            yield from _walk(sub, child_path, seen)
        return

    if isinstance(value, (list, tuple, set)):
        for index, sub in enumerate(value):
            yield from _walk(sub, f"{path}[{index}]", seen)
        return

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        yield from _walk(dataclasses.asdict(value), path, seen)
        return

    # Pydantic model.
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            yield from _walk(dump(), path, seen)
            return
        except Exception:
            pass

    inner = getattr(value, "__dict__", None)
    if isinstance(inner, dict) and inner:
        yield from _walk(inner, path, seen)


def find_secrets(value: Any) -> list[SecretFinding]:
    """Every place a secret was detected in ``value``, by path. Empty is clean."""
    return list(_walk(value, "", set()))


def assert_no_secrets(value: Any, *, where: str = "value") -> None:
    """Raise if ``value`` carries anything secret-shaped. The firewall as a
    defense-in-depth guard, usable before a value crosses a boundary."""
    findings = find_secrets(value)
    if findings:
        rendered = ", ".join(f"{f.path} ({f.why})" for f in findings[:8])
        raise AssertionError(
            f"secret material detected in {where}: {rendered}"
        )
