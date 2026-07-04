"""
CortexPrime Neo4j Cognitive Graph Infrastructure
=================================================
Public API for the Neo4j graph layer.

Singletons:
  neo4j_connection        — async driver wrapper
  neo4j_graph             — backward-compat manager (schema + upsert helpers)
  agent_repository        — Agent node CRUD + dependency graphs
  execution_repository    — Execution lineage + stage tracking
  memory_repository       — Memory nodes + relationship management
  cognition_repository    — CognitionEvent + Reflection nodes
  world_model_repository  — WorldModel + Concept nodes
  graph_traversal         — Advanced path/traversal algorithms
  graph_query_service     — High-level cross-domain query façade

Schema constants:
  Labels, Rels, Props, SCHEMA_STATEMENTS
"""

from backend.infrastructure.neo4j.connection import neo4j_connection
from backend.infrastructure.neo4j.graph_manager import neo4j_graph
from backend.infrastructure.neo4j.schema import Labels, Rels, Props, SCHEMA_STATEMENTS
from backend.infrastructure.neo4j.traversal import graph_traversal
from backend.infrastructure.neo4j.query_service import graph_query_service

from backend.infrastructure.neo4j.repositories.agent_repository import (
    AgentRepository, agent_repository,
)
from backend.infrastructure.neo4j.repositories.execution_repository import (
    ExecutionRepository, execution_repository,
)
from backend.infrastructure.neo4j.repositories.memory_repository import (
    MemoryRepository, memory_repository,
)
from backend.infrastructure.neo4j.repositories.cognition_repository import (
    CognitionRepository, cognition_repository,
)
from backend.infrastructure.neo4j.repositories.world_model_repository import (
    WorldModelRepository, world_model_repository,
)

__all__ = [
    # Singletons
    "neo4j_connection",
    "neo4j_graph",
    "agent_repository",
    "execution_repository",
    "memory_repository",
    "cognition_repository",
    "world_model_repository",
    "graph_traversal",
    "graph_query_service",
    # Classes
    "AgentRepository",
    "ExecutionRepository",
    "MemoryRepository",
    "CognitionRepository",
    "WorldModelRepository",
    # Schema
    "Labels",
    "Rels",
    "Props",
    "SCHEMA_STATEMENTS",
]

