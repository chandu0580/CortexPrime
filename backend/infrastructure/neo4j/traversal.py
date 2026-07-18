"""
Graph Traversal Engine
======================
Advanced Cypher-based traversal algorithms for the cognitive graph:
shortest paths, influence analysis, memory context expansion,
semantic neighborhoods, and execution impact analysis.

All methods are safe no-ops when Neo4j is unavailable.
All Cypher queries use parameterised inputs to prevent injection.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.infrastructure.neo4j.repositories.base_repository import BaseRepository
from backend.infrastructure.neo4j.schema import Rels

log = logging.getLogger(__name__)


class GraphTraversal(BaseRepository):
    """
    Collection of graph traversal algorithms over the cognitive graph.

    Designed to be used directly by the QueryService, not by callers
    that want individual node/relationship operations (use the
    repositories for that).
    """

    # ------------------------------------------------------------------
    # Agent graph traversals
    # ------------------------------------------------------------------

    async def shortest_path_between_agents(
        self,
        from_agent: str,
        to_agent: str,
        max_depth: int = 6,
    ) -> List[Dict[str, Any]]:
        """
        Find the shortest path(s) between two agents through any
        relationship type.  Returns ordered list of node identifiers.
        """
        return await self._run(
            """
            MATCH path = shortestPath(
                (a:Agent {name: $from_agent})-[*1..$max_depth]-(b:Agent {name: $to_agent})
            )
            RETURN [n IN nodes(path) | coalesce(n.name, n.execution_id, n.memory_id, n.event_id)] AS path_nodes,
                   [r IN relationships(path) | type(r)] AS path_rels,
                   length(path) AS path_length
            """,
            from_agent=from_agent,
            to_agent=to_agent,
            max_depth=max_depth,
        )

    async def get_influence_graph(
        self,
        agent_name: str,
        depth: int = 3,
    ) -> Dict[str, Any]:
        """
        Return the subgraph of agents that *agent_name* influences
        (outbound FEEDS edges) and agents that influence it (inbound).
        """
        downstream = await self._run(
            f"""
            MATCH path = (root:Agent {{name: $agent_name}})
                         -[:{Rels.FEEDS}*1..$depth]->(influenced:Agent)
            RETURN influenced.name AS name,
                   influenced.type AS type,
                   length(path)    AS depth,
                   count(*) AS edge_count
            ORDER BY depth ASC
            """,
            agent_name=agent_name,
            depth=depth,
        )
        upstream = await self._run(
            f"""
            MATCH path = (influencer:Agent)
                         -[:{Rels.FEEDS}*1..$depth]->(root:Agent {{name: $agent_name}})
            RETURN influencer.name AS name,
                   influencer.type AS type,
                   length(path)    AS depth
            ORDER BY depth ASC
            """,
            agent_name=agent_name,
            depth=depth,
        )
        return {
            "agent": agent_name,
            "downstream_influences": downstream,
            "upstream_influences": upstream,
        }

    async def get_agent_centrality(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Approximate degree-centrality for Agent nodes:
        in-degree (how many agents feed into this one) +
        out-degree (how many this one feeds).
        """
        return await self._run(
            f"""
            MATCH (a:Agent)
            OPTIONAL MATCH (a)<-[inr:{Rels.FEEDS}]-()
            OPTIONAL MATCH (a)-[outr:{Rels.FEEDS}]->()
            RETURN a.name          AS name,
                   a.type          AS type,
                   count(DISTINCT inr)  AS in_degree,
                   count(DISTINCT outr) AS out_degree,
                   count(DISTINCT inr) + count(DISTINCT outr) AS centrality
            ORDER BY centrality DESC
            LIMIT $limit
            """,
            limit=limit,
        )

    # ------------------------------------------------------------------
    # Memory traversals
    # ------------------------------------------------------------------

    async def expand_memory_context(
        self,
        memory_id: str,
        depth: int = 2,
        limit: int = 30,
        include_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Expand the context around a memory: return all memories,
        concepts, and executions reachable within *depth* hops.
        Optionally filter by memory type.
        """
        if include_types:
            type_filter = "AND m.type IN $include_types"
        else:
            type_filter = ""

        return await self._run(
            f"""
            MATCH path = (start:Memory {{memory_id: $memory_id}})-[*1..$depth]-(node)
            WHERE (node:Memory OR node:Concept OR node:Execution)
            {type_filter if include_types else ""}
            WITH DISTINCT node, min(length(path)) AS distance
            RETURN labels(node)[0]                              AS node_type,
                   coalesce(node.memory_id, node.name, node.execution_id) AS node_id,
                   coalesce(node.content, node.description, node.objective, '') AS summary,
                   distance
            ORDER BY distance ASC
            LIMIT $limit
            """,
            memory_id=memory_id,
            depth=depth,
            limit=limit,
            **({"include_types": include_types} if include_types else {}),
        )

    async def get_memory_chain(
        self,
        root_memory_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Follow TRIGGERED edges from *root_memory_id* to get the
        causal chain of memories it generated.
        """
        return await self._run(
            f"""
            MATCH path = (start:Memory {{memory_id: $root_id}})
                         -[:{Rels.TRIGGERED}*1..20]->(child:Memory)
            RETURN child.memory_id  AS memory_id,
                   child.type       AS type,
                   child.agent      AS agent,
                   child.content    AS content,
                   length(path)     AS depth
            ORDER BY depth ASC
            LIMIT $limit
            """,
            root_id=root_memory_id,
            limit=limit,
        )

    async def get_semantic_neighborhood(
        self,
        concept_name: str,
        depth: int = 2,
        limit: int = 40,
    ) -> Dict[str, Any]:
        """
        Return the full semantic neighborhood of a concept:
        related concepts, memories that are instances of it,
        and world models it belongs to.
        """
        related_concepts = await self._run(
            """
            MATCH path = (start:Concept {name: $concept_name})-[*1..$depth]-(c:Concept)
            WHERE c.name <> $concept_name
            RETURN DISTINCT c.name        AS name,
                            c.domain      AS domain,
                            c.description AS description,
                            min(length(path)) AS distance
            ORDER BY distance ASC
            LIMIT $limit
            """,
            concept_name=concept_name,
            depth=depth,
            limit=limit,
        )
        instance_memories = await self._run(
            f"""
            MATCH (m:Memory)-[:{Rels.INSTANCE_OF}]->(c:Concept {{name: $concept_name}})
            RETURN m.memory_id AS memory_id,
                   m.type      AS type,
                   m.agent     AS agent,
                   m.content   AS content
            LIMIT 20
            """,
            concept_name=concept_name,
        )
        world_models = await self._run(
            f"""
            MATCH (c:Concept {{name: $concept_name}})-[:{Rels.PART_OF_MODEL}]->(wm:WorldModel)
            RETURN wm.model_id AS model_id,
                   wm.name     AS name,
                   wm.domain   AS domain
            """,
            concept_name=concept_name,
        )
        return {
            "concept": concept_name,
            "related_concepts": related_concepts,
            "instance_memories": instance_memories,
            "world_models": world_models,
        }

    # ------------------------------------------------------------------
    # Execution impact analysis
    # ------------------------------------------------------------------

    async def get_execution_impact(
        self,
        execution_id: str,
        depth: int = 3,
    ) -> Dict[str, Any]:
        """
        Analyse the full downstream impact of an execution:
        - All spawned child executions
        - All memories produced during this execution
        - All concepts extracted
        - All agents involved
        - All cognition events triggered
        """
        children = await self._run(
            f"""
            MATCH path = (root:Execution {{execution_id: $execution_id}})
                         -[:{Rels.SPAWNED}*1..$depth]->(child:Execution)
            RETURN child.execution_id AS execution_id,
                   child.objective    AS objective,
                   child.status       AS status,
                   length(path)       AS depth
            ORDER BY depth ASC
            """,
            execution_id=execution_id,
            depth=depth,
        )
        memories = await self._run(
            f"""
            MATCH (m:Memory)-[:{Rels.PART_OF}]->(e:Execution {{execution_id: $execution_id}})
            RETURN m.memory_id AS memory_id,
                   m.type      AS type,
                   m.agent     AS agent
            """,
            execution_id=execution_id,
        )
        agents = await self._run(
            f"""
            MATCH (e:Execution {{execution_id: $execution_id}})
                  -[r:{Rels.EXECUTED_BY}]->(a:Agent)
            RETURN DISTINCT a.name AS name,
                            a.type AS type,
                            r.stage AS stage
            """,
            execution_id=execution_id,
        )
        concepts = await self._run(
            f"""
            MATCH (c:Concept)-[:{Rels.INFORMED_BY}]->(e:Execution {{execution_id: $execution_id}})
            RETURN c.name   AS name,
                   c.domain AS domain
            """,
            execution_id=execution_id,
        )
        cognition_events = await self._run(
            f"""
            MATCH (e:Execution {{execution_id: $execution_id}})
                  -[:{Rels.TRIGGERED_COGNITION}]->(ce:CognitionEvent)
            RETURN ce.event_id   AS event_id,
                   ce.event_type AS event_type,
                   ce.agent      AS agent
            ORDER BY ce.created_at ASC
            """,
            execution_id=execution_id,
        )
        return {
            "execution_id": execution_id,
            "child_executions": children,
            "memories_produced": memories,
            "agents_involved": agents,
            "concepts_extracted": concepts,
            "cognition_events": cognition_events,
        }

    async def get_execution_replay_lineage(
        self,
        execution_id: str,
        depth: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Return the complete ordered lineage needed to replay an execution:
        all ancestor + descendant executions with stage information.
        """
        return await self._run(
            f"""
            // Ancestors
            MATCH anc_path = (anc:Execution)<-[:{Rels.SPAWNED}*0..$depth]-(target:Execution {{execution_id: $execution_id}})
            WITH collect(DISTINCT {{
                execution_id: anc.execution_id,
                objective: anc.objective,
                status: anc.status,
                direction: 'ancestor',
                depth: -length(anc_path)
            }}) AS ancestors

            // Descendants
            MATCH desc_path = (target2:Execution {{execution_id: $execution_id}})-[:{Rels.SPAWNED}*0..$depth]->(desc:Execution)
            WITH ancestors, collect(DISTINCT {{
                execution_id: desc.execution_id,
                objective: desc.objective,
                status: desc.status,
                direction: 'descendant',
                depth: length(desc_path)
            }}) AS descendants

            RETURN ancestors + descendants AS lineage
            """,
            execution_id=execution_id,
            depth=depth,
        )


# Singleton
graph_traversal = GraphTraversal()
