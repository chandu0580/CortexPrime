"""Contract base machinery: identity, versioning, and serialization.

This module defines how every CortexPrime contract is named, versioned, and
converted to and from a transport-neutral dictionary. It contains no domain
vocabulary of its own.

Design notes
------------
Contracts are plain ``dataclasses.dataclass(frozen=True)`` subclasses of
:class:`Contract`. ``Contract`` is deliberately *not* itself a dataclass so
that subclasses can define fields freely without inheriting ordering
constraints.

Serialization uses an explicit envelope rather than bare field dictionaries::

    {"_contract": "cortexprime.approval.artifact", "_version": 1, ...fields}

The envelope is what makes cross-version decoding possible: a receiver can
inspect ``_contract`` and ``_version`` before attempting to interpret any
field. See ADR-010.

Determinism
-----------
``to_dict`` emits keys in declaration order and converts values through a
fixed, total mapping (see :func:`_encode_value`). This makes the output
suitable as input to a canonical hashing routine. The contracts package does
**not** perform hashing itself -- that is platform infrastructure (PR-02).
"""

from __future__ import annotations

import dataclasses
import types
import typing
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, ClassVar, Mapping, TypeVar, get_args, get_origin

from backend.contracts.errors import ContractViolation, ContractVersionError

__all__ = [
    "Contract",
    "ENVELOPE_CONTRACT_KEY",
    "ENVELOPE_VERSION_KEY",
    "FrozenDict",
    "contract_registry",
    "decode_envelope",
    "freeze_mapping",
]

ENVELOPE_CONTRACT_KEY = "_contract"
ENVELOPE_VERSION_KEY = "_version"

_REGISTRY: dict[str, type["Contract"]] = {}

TContract = TypeVar("TContract", bound="Contract")


class FrozenDict(Mapping[str, Any]):
    """An immutable, hashable mapping.

    ``types.MappingProxyType`` is read-only but *not* hashable, which silently
    makes any frozen dataclass containing one unhashable too -- so a contract
    carrying an opaque bag could not be used as a dict key or put in a set
    despite being immutable in every other respect.

    Hashing is by canonicalized content: keys are sorted, and nested mappings
    and sequences are normalized so that two equal bags hash identically
    regardless of insertion order. Values must themselves be hashable after that
    normalization, which is true of every primitive contracts permit.

    The hash is computed once and cached, because the contents cannot change.
    """

    __slots__ = ("_data", "_hash")

    def __init__(self, data: Mapping[str, Any] | None = None) -> None:
        object.__setattr__(self, "_data", dict(data or {}))
        object.__setattr__(self, "_hash", None)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"FrozenDict({self._data!r})"

    def __setitem__(self, key: str, value: Any) -> None:
        raise TypeError("FrozenDict is immutable")

    def __delitem__(self, key: str) -> None:
        raise TypeError("FrozenDict is immutable")

    @staticmethod
    def _hashable(value: Any) -> Any:
        if isinstance(value, Mapping):
            return tuple(sorted((key, FrozenDict._hashable(item)) for key, item in value.items()))
        if isinstance(value, (list, tuple)):
            return tuple(FrozenDict._hashable(item) for item in value)
        return value

    def __hash__(self) -> int:
        cached = self._hash
        if cached is None:
            cached = hash(self._hashable(self._data))
            object.__setattr__(self, "_hash", cached)
        return cached

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mapping):
            return dict(self._data) == dict(other)
        return NotImplemented


def freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Return an immutable, hashable view of ``value``.

    Contracts that must carry opaque caller-supplied data (an execution
    payload, an audit detail bag) use this to preserve immutability. The
    returned mapping rejects mutation at runtime and remains hashable, so the
    contract containing it stays usable as a dict key.

    ``None`` is normalized to an empty mapping so that consumers never need a
    null check on an opaque bag. The input is copied, so a caller retaining a
    reference cannot reach in afterwards.
    """
    if value is None:
        return FrozenDict()
    if isinstance(value, FrozenDict):
        return value
    if not isinstance(value, Mapping):
        raise ContractViolation(f"expected a mapping, received {type(value).__name__}")
    return FrozenDict(value)


def _encode_value(value: Any) -> Any:
    """Convert a contract field value into a transport-neutral primitive.

    The mapping is total over the field types contracts are permitted to use.
    Anything else raises, which surfaces unsupported field types at the moment
    a contract is first serialized rather than silently emitting garbage.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ContractViolation("naive datetime cannot be serialized; use timezone-aware UTC")
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Contract):
        return value.to_dict()
    if isinstance(value, (tuple, list)):
        return [_encode_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _encode_value(item) for key, item in value.items()}
    raise ContractViolation(f"unsupported contract field type: {type(value).__name__}")


def _unwrap_optional(annotation: Any) -> tuple[Any, bool]:
    """Split ``T | None`` into ``(T, True)``; leave other annotations alone."""
    origin = get_origin(annotation)
    if origin is typing.Union or origin is types.UnionType:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return args[0], True
        raise ContractViolation(f"unions other than Optional are not permitted: {annotation}")
    return annotation, False


def _decode_value(annotation: Any, value: Any) -> Any:
    """Convert a transport primitive back into the annotated field type."""
    annotation, optional = _unwrap_optional(annotation)
    if value is None:
        if not optional:
            raise ContractViolation(f"missing value for non-optional field of type {annotation}")
        return None

    origin = get_origin(annotation)

    if origin in (tuple, list):
        args = get_args(annotation)
        if not args:
            raise ContractViolation("collection fields must declare an element type")
        element = args[0]
        if not isinstance(value, (list, tuple)):
            raise ContractViolation(f"expected a sequence, received {type(value).__name__}")
        return tuple(_decode_value(element, item) for item in value)

    if origin in (dict, Mapping, types.MappingProxyType, FrozenDict) or annotation in (
        Mapping,
        FrozenDict,
    ):
        if not isinstance(value, Mapping):
            raise ContractViolation(f"expected a mapping, received {type(value).__name__}")
        return freeze_mapping(dict(value))

    if isinstance(annotation, type):
        if issubclass(annotation, Contract):
            return annotation.from_dict(value)
        if issubclass(annotation, Enum):
            try:
                return annotation(value)
            except ValueError as exc:
                raise ContractViolation(f"{value!r} is not a valid {annotation.__name__}") from exc
        if annotation is datetime:
            return _decode_datetime(value)
        if annotation is date:
            return date.fromisoformat(value)
        if annotation in (bool, int, float, str):
            if not isinstance(value, annotation):
                raise ContractViolation(
                    f"expected {annotation.__name__}, received {type(value).__name__}"
                )
            return value

    # Any / object / unparameterized -- pass through untouched.
    return value


def _decode_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ContractViolation(f"expected an ISO-8601 string, received {type(value).__name__}")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ContractViolation(f"invalid ISO-8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ContractViolation(f"timestamp must carry a timezone: {value!r}")
    return parsed.astimezone(timezone.utc)


class Contract:
    """Base class for every CortexPrime contract.

    Subclasses must be declared as ``@dataclass(frozen=True)`` and must set
    ``CONTRACT_NAME``. ``CONTRACT_VERSION`` defaults to 1 and is incremented
    only for breaking changes (see the backward-compatibility rules in
    ``docs/contracts/README.md``).
    """

    CONTRACT_NAME: ClassVar[str]
    CONTRACT_VERSION: ClassVar[int] = 1

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        name = cls.__dict__.get("CONTRACT_NAME")
        if name is None:
            # Intermediate/abstract bases are permitted to omit a name; they
            # simply are not registered and cannot be decoded by name.
            return
        if not isinstance(name, str) or not name:
            raise ContractViolation(f"{cls.__name__}.CONTRACT_NAME must be a non-empty string")
        existing = _REGISTRY.get(name)
        if existing is not None and existing is not cls:
            raise ContractViolation(
                f"duplicate CONTRACT_NAME {name!r}: {existing.__name__} and {cls.__name__}"
            )
        _REGISTRY[name] = cls

    def to_dict(self) -> dict[str, Any]:
        """Serialize to an enveloped, transport-neutral dictionary."""
        if not dataclasses.is_dataclass(self):
            raise ContractViolation(f"{type(self).__name__} must be a dataclass")
        payload: dict[str, Any] = {
            ENVELOPE_CONTRACT_KEY: type(self).CONTRACT_NAME,
            ENVELOPE_VERSION_KEY: type(self).CONTRACT_VERSION,
        }
        for field in dataclasses.fields(self):
            payload[field.name] = _encode_value(getattr(self, field.name))
        return payload

    @classmethod
    def from_dict(cls: type[TContract], data: Mapping[str, Any]) -> TContract:
        """Reconstruct a contract from :meth:`to_dict` output.

        The envelope is validated before any field is interpreted. A payload
        declaring a *newer* version raises :class:`ContractVersionError`;
        a payload declaring an *older* version is accepted, because contract
        evolution is additive-only and older payloads are by construction a
        subset of the current shape.
        """
        if not isinstance(data, Mapping):
            raise ContractViolation(f"expected a mapping, received {type(data).__name__}")

        declared_name = data.get(ENVELOPE_CONTRACT_KEY)
        if declared_name is not None and declared_name != cls.CONTRACT_NAME:
            raise ContractViolation(
                f"envelope declares {declared_name!r} but {cls.__name__} "
                f"expects {cls.CONTRACT_NAME!r}"
            )

        declared_version = data.get(ENVELOPE_VERSION_KEY, cls.CONTRACT_VERSION)
        if not isinstance(declared_version, int):
            raise ContractViolation(f"envelope version must be an integer, got {declared_version!r}")
        if declared_version > cls.CONTRACT_VERSION:
            raise ContractVersionError(
                f"{cls.CONTRACT_NAME} payload is version {declared_version} but this build "
                f"understands at most version {cls.CONTRACT_VERSION}"
            )

        hints = typing.get_type_hints(cls)
        kwargs: dict[str, Any] = {}
        for field in dataclasses.fields(cls):  # type: ignore[arg-type]
            annotation = hints.get(field.name, Any)
            if field.name in data:
                kwargs[field.name] = _decode_value(annotation, data[field.name])
            elif field.default is not dataclasses.MISSING or (
                field.default_factory is not dataclasses.MISSING  # type: ignore[misc]
            ):
                continue  # dataclass default applies
            else:
                raise ContractViolation(
                    f"{cls.CONTRACT_NAME} payload is missing required field {field.name!r}"
                )
        return cls(**kwargs)


def contract_registry() -> Mapping[str, type[Contract]]:
    """Return a read-only view of every registered contract, keyed by name."""
    return types.MappingProxyType(dict(_REGISTRY))


def decode_envelope(data: Mapping[str, Any]) -> Contract:
    """Decode an enveloped payload without knowing its type in advance.

    Used by transport layers that receive heterogeneous messages.
    """
    if not isinstance(data, Mapping):
        raise ContractViolation(f"expected a mapping, received {type(data).__name__}")
    name = data.get(ENVELOPE_CONTRACT_KEY)
    if not isinstance(name, str):
        raise ContractViolation(f"envelope is missing {ENVELOPE_CONTRACT_KEY!r}")
    contract_type = _REGISTRY.get(name)
    if contract_type is None:
        raise ContractViolation(f"unknown contract {name!r}")
    return contract_type.from_dict(data)
