"""Capability Fabric infrastructure. In-memory; the Protocol is the seam."""

from backend.contexts.connectivity.infrastructure.binding_repository import (
    BINDING_STORAGE_BINDING,
    BindingRepository,
    InMemoryBindingRepository,
)
from backend.contexts.connectivity.infrastructure.persistence import (
    RECORD_SCHEMA_VERSION,
    from_record,
    to_record,
)
from backend.contexts.connectivity.infrastructure.repository import (
    CAPABILITY_BINDING,
    CapabilityRepository,
    InMemoryCapabilityRepository,
)

__all__ = [
    "BindingRepository",
    "InMemoryBindingRepository",
    "BINDING_STORAGE_BINDING",
    "CapabilityRepository",
    "InMemoryCapabilityRepository",
    "CAPABILITY_BINDING",
    "RECORD_SCHEMA_VERSION",
    "to_record",
    "from_record",
]
