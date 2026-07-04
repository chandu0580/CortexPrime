"""
CortexPrime Neo4j Graph Schema
================================
Centralised constants for node labels, relationship types,
property names, and Cypher schema bootstrap statements.

Design decisions:
- All label/relationship strings come from this module; no string
  literals scattered across the codebase.
- MERGE keys (the property used in ``MERGE (n:Label {key: $val})``)
  are documented per label to make index/constraint reasoning clear.
- All constraint/index DDL is collected in ``SCHEMA_STATEMENTS`` so
  a single call to ``ensure_schema()`` is all that's needed at startup.
"""
from __future__ import annotations

from typing import Final, List


# ===========================================================================
# NODE LABELS
# ===========================================================================

class Labels:
    """Neo4j node labels used across the cognitive graph."""

    AGENT: Final           = "Agent"
    EXECUTION: Final       = "Execution"
    MEMORY: Final          = "Memory"
    CONCEPT: Final         = "Concept"
    TASK: Final            = "Task"
    COGNITION_EVENT: Final = "CognitionEvent"
    WORLD_MODEL: Final     = "WorldModel"
    MISSION: Final         = "Mission"
    REFLECTION: Final      = "Reflection"
    PIPELINE: Final        = "Pipeline"


# ===========================================================================
# RELATIONSHIP TYPES
# ===========================================================================

class Rels:
    """Neo4j relationship type constants."""

    # Agent ↔ Agent
    FEEDS: Final       = "FEEDS"         # agent output consumed by another
    DEPENDS_ON: Final  = "DEPENDS_ON"    # static capability dependency
    COLLABORATES: Final = "COLLABORATES" # co-execution collaboration

    # Execution lineage
    SPAWNED: Final     = "SPAWNED"       # parent execution → child execution
    EXECUTED_BY: Final = "EXECUTED_BY"   # execution step → agent
    PART_OF: Final     = "PART_OF"       # memory/task → mission/execution

    # Memory relationships
    PRODUCED: Final       = "PRODUCED"       # agent → memory
    REFERENCED: Final     = "REFERENCED"     # memory → memory (citation)
    SIMILAR_TO: Final     = "SIMILAR_TO"     # semantic similarity edge
    TRIGGERED: Final      = "TRIGGERED"      # memory → memory (causal)
    REFLECTS_ON: Final    = "REFLECTS_ON"    # reflection → memory/execution
    RETRIEVED_BY: Final   = "RETRIEVED_BY"   # memory → agent (retrieval event)

    # Concept / World-model
    RELATED_TO: Final     = "RELATED_TO"     # generic semantic relationship
    INSTANCE_OF: Final    = "INSTANCE_OF"    # memory/task → concept
    PART_OF_MODEL: Final  = "PART_OF_MODEL"  # concept → world model
    INFORMED_BY: Final    = "INFORMED_BY"    # world model updated by execution

    # Cognition pipeline
    FLOWS_TO: Final       = "FLOWS_TO"       # cognition event → next event
    TRIGGERED_COGNITION: Final = "TRIGGERED_COGNITION"  # execution → cognition event

    # Pipeline
    STAGE_OF: Final       = "STAGE_OF"       # task → pipeline


# ===========================================================================
# PROPERTY NAME CONSTANTS
# ===========================================================================

class Props:
    """Commonly used property keys."""

    # Identity
    NAME: Final         = "name"
    ID: Final           = "id"
    EXECUTION_ID: Final = "execution_id"
    MEMORY_ID: Final    = "memory_id"
    MISSION_ID: Final   = "mission_id"
    CONCEPT: Final      = "concept"

    # Classification
    TYPE: Final         = "type"
    STAGE: Final        = "stage"
    STATUS: Final       = "status"
    PRIORITY: Final     = "priority"

    # Content
    CONTENT: Final      = "content"
    OBJECTIVE: Final    = "objective"
    DESCRIPTION: Final  = "description"
    SUMMARY: Final      = "summary"

    # Metrics
    DURATION_MS: Final  = "duration_ms"
    CONFIDENCE: Final   = "confidence"
    WEIGHT: Final       = "weight"

    # Timestamps
    CREATED_AT: Final   = "created_at"
    UPDATED_AT: Final   = "updated_at"
    COMPLETED_AT: Final = "completed_at"
    EXECUTED_AT: Final  = "executed_at"


# ===========================================================================
# SCHEMA BOOTSTRAP DDL
# ===========================================================================

# All statements are idempotent (IF NOT EXISTS).
# Order matters only in the sense that constraints must exist before
# the matching indexes are created — constraints implicitly create an
# index on the constrained property, so we list them first.

CONSTRAINT_STATEMENTS: List[str] = [
    # Unique node identity constraints
    "CREATE CONSTRAINT agent_name IF NOT EXISTS "
    "FOR (a:Agent) REQUIRE a.name IS UNIQUE",

    "CREATE CONSTRAINT execution_id IF NOT EXISTS "
    "FOR (e:Execution) REQUIRE e.execution_id IS UNIQUE",

    "CREATE CONSTRAINT memory_id IF NOT EXISTS "
    "FOR (m:Memory) REQUIRE m.memory_id IS UNIQUE",

    "CREATE CONSTRAINT concept_name IF NOT EXISTS "
    "FOR (c:Concept) REQUIRE c.name IS UNIQUE",

    "CREATE CONSTRAINT mission_id IF NOT EXISTS "
    "FOR (ms:Mission) REQUIRE ms.mission_id IS UNIQUE",

    "CREATE CONSTRAINT world_model_id IF NOT EXISTS "
    "FOR (wm:WorldModel) REQUIRE wm.model_id IS UNIQUE",

    "CREATE CONSTRAINT cognition_event_id IF NOT EXISTS "
    "FOR (ce:CognitionEvent) REQUIRE ce.event_id IS UNIQUE",

    "CREATE CONSTRAINT reflection_id IF NOT EXISTS "
    "FOR (r:Reflection) REQUIRE r.reflection_id IS UNIQUE",
]

INDEX_STATEMENTS: List[str] = [
    # Lookup indexes
    "CREATE INDEX agent_type IF NOT EXISTS "
    "FOR (a:Agent) ON (a.type)",

    "CREATE INDEX execution_status IF NOT EXISTS "
    "FOR (e:Execution) ON (e.status)",

    "CREATE INDEX execution_created IF NOT EXISTS "
    "FOR (e:Execution) ON (e.created_at)",

    "CREATE INDEX memory_type IF NOT EXISTS "
    "FOR (m:Memory) ON (m.type)",

    "CREATE INDEX memory_agent IF NOT EXISTS "
    "FOR (m:Memory) ON (m.agent)",

    "CREATE INDEX cognition_event_type IF NOT EXISTS "
    "FOR (ce:CognitionEvent) ON (ce.event_type)",

    "CREATE INDEX concept_domain IF NOT EXISTS "
    "FOR (c:Concept) ON (c.domain)",

    # Full-text indexes for semantic search
    "CREATE FULLTEXT INDEX memory_content_fts IF NOT EXISTS "
    "FOR (m:Memory) ON EACH [m.content]",

    "CREATE FULLTEXT INDEX concept_desc_fts IF NOT EXISTS "
    "FOR (c:Concept) ON EACH [c.description, c.name]",
]

# Combined list used by ensure_schema()
SCHEMA_STATEMENTS: List[str] = CONSTRAINT_STATEMENTS + INDEX_STATEMENTS
