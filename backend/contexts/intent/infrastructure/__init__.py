"""Infrastructure: the repository and the record mapping."""

from backend.contexts.intent.infrastructure.persistence import (
    RECORD_SCHEMA_VERSION,
    from_record,
    to_record,
)
from backend.contexts.intent.infrastructure.repository import (
    INTENT_BINDING,
    InMemoryIntentRepository,
    IntentRepository,
)

__all__ = [
    "IntentRepository",
    "InMemoryIntentRepository",
    "INTENT_BINDING",
    "RECORD_SCHEMA_VERSION",
    "to_record",
    "from_record",
]
