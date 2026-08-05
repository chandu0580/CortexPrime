"""Canonical serialization: one byte sequence per logical value.

Two structures that are logically equal must produce identical bytes, or every
guarantee built on hashing collapses. In particular, Constitution I2 -- the
approved payload is the executed payload, proven by digest -- is only as strong
as the determinism of this module.

The canonical form
------------------
A restricted, fully-specified JSON dialect:

======================  ======================================================
Object keys             Sorted by UTF-8 code point. Non-string keys rejected.
Whitespace              None. No spaces after ``:`` or ``,``.
Strings                 JSON escaping, non-ASCII emitted literally as UTF-8.
Integers                Decimal, no leading zeros or ``+``.
Booleans                ``true`` / ``false`` -- checked *before* int, because
                        ``isinstance(True, int)`` is True in Python.
Floats                  Shortest round-tripping repr. NaN and +/-Infinity are
                        rejected: JSON cannot represent them.
Null                    ``null``
Sequences               ``list`` and ``tuple`` both serialize as JSON arrays.
                        Order is significant and preserved.
Encoding                UTF-8, no BOM.
======================  ======================================================

Known limitation, stated plainly
--------------------------------
Float formatting uses Python's shortest-round-trip repr. That is stable across
CPython 3.x but is **not** guaranteed byte-identical in another language's
runtime. CortexPrime is Python-only by decision (ADR-010 rejected Protocol
Buffers on those grounds), so this is acceptable today. If a non-Python client
ever needs to verify a digest, floats must move to a fixed decimal encoding and
``CANONICAL_VERSION`` must increment.

Versioning
----------
``CANONICAL_VERSION`` identifies the ruleset above. Any change to those rules is
breaking -- previously computed digests would no longer reproduce -- and
requires an increment plus an ADR. The version is mixed into every digest via
domain separation (see ``digest.py``), so a v1 digest and a v2 digest of the
same value differ, which is the intended behavior rather than a hazard.
"""

from __future__ import annotations

import math
from typing import Any, Final, Mapping, Sequence

__all__ = [
    "CANONICAL_VERSION",
    "CanonicalizationError",
    "canonical_bytes",
    "canonical_text",
]

CANONICAL_VERSION: Final[int] = 1
"""Version of the canonicalization ruleset. Changing the rules breaks every
previously computed digest and requires an ADR."""

_MAX_DEPTH: Final[int] = 64
"""Guards against pathological nesting and against cycles that would otherwise
recurse until the interpreter's stack limit. Contracts nest a handful of levels
deep; 64 is far beyond any legitimate structure."""

_ESCAPES: Final[dict[int, str]] = {
    0x22: '\\"',
    0x5C: "\\\\",
    0x08: "\\b",
    0x0C: "\\f",
    0x0A: "\\n",
    0x0D: "\\r",
    0x09: "\\t",
}


class CanonicalizationError(ValueError):
    """A value cannot be canonicalized deterministically.

    Raised rather than silently coercing. A value we cannot serialize the same
    way twice must never reach a digest, because the resulting hash would be
    unverifiable.
    """


def _escape_string(value: str) -> str:
    out: list[str] = ['"']
    for character in value:
        code = ord(character)
        escape = _ESCAPES.get(code)
        if escape is not None:
            out.append(escape)
        elif code < 0x20:
            out.append(f"\\u{code:04x}")
        else:
            # Non-ASCII is emitted literally; UTF-8 encoding happens once, at
            # the end. Escaping it would be equally deterministic but larger.
            out.append(character)
    out.append('"')
    return "".join(out)


def _format_float(value: float) -> str:
    if math.isnan(value) or math.isinf(value):
        raise CanonicalizationError(
            f"{value!r} cannot be canonicalized: JSON has no representation for "
            "NaN or Infinity"
        )
    if value == int(value) and abs(value) < 1e16:
        # Emit 1.0 as "1.0", never "1", so a float and an int never collide.
        return f"{int(value)}.0"
    return repr(value)


def _write(value: Any, out: list[str], depth: int) -> None:
    if depth > _MAX_DEPTH:
        raise CanonicalizationError(
            f"structure exceeds maximum depth of {_MAX_DEPTH}; this usually means a cycle"
        )

    if value is None:
        out.append("null")
        return

    # bool must precede int: isinstance(True, int) is True in Python.
    if isinstance(value, bool):
        out.append("true" if value else "false")
        return

    if isinstance(value, int):
        out.append(str(value))
        return

    if isinstance(value, float):
        out.append(_format_float(value))
        return

    if isinstance(value, str):
        out.append(_escape_string(value))
        return

    if isinstance(value, Mapping):
        keys = list(value.keys())
        for key in keys:
            if not isinstance(key, str):
                raise CanonicalizationError(
                    f"object keys must be strings; found {type(key).__name__}"
                )
        out.append("{")
        for index, key in enumerate(sorted(keys)):
            if index:
                out.append(",")
            out.append(_escape_string(key))
            out.append(":")
            _write(value[key], out, depth + 1)
        out.append("}")
        return

    # str and bytes are Sequences too, so they must already have been handled.
    if isinstance(value, (list, tuple)) or (
        isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
    ):
        out.append("[")
        for index, item in enumerate(value):
            if index:
                out.append(",")
            _write(item, out, depth + 1)
        out.append("]")
        return

    raise CanonicalizationError(
        f"{type(value).__name__} has no canonical form. Convert it to a primitive "
        "before hashing -- silently coercing here would produce a digest nobody "
        "can reproduce."
    )


def canonical_text(value: Any) -> str:
    """Return the canonical string form of ``value``.

    Raises :class:`CanonicalizationError` for anything without a deterministic
    representation. Prefer :func:`canonical_bytes` when feeding a hash.
    """
    out: list[str] = []
    _write(value, out, depth=0)
    return "".join(out)


def canonical_bytes(value: Any) -> bytes:
    """Return the canonical UTF-8 bytes of ``value``.

    This is the input to every digest CortexPrime computes.
    """
    return canonical_text(value).encode("utf-8")
