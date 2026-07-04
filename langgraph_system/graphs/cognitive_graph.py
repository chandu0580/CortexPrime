from langgraph.graph import (
    StateGraph,
    END
)

from langgraph_system.state_management.cognitive_state import (
    CognitiveState
)

from langgraph_system.nodes.research_node import (
    research_node
)

from langgraph_system.nodes.planner_node import (
    planner_node
)

from langgraph_system.nodes.critic_node import (
    critic_node
)

from langgraph_system.nodes.optimizer_node import (
    optimizer_node
)

from langgraph_system.graphs.graph_router import (
    reflection_router
)


# ==========================================
# INITIALIZE GRAPH
# ==========================================

workflow = StateGraph(
    CognitiveState
)

# ==========================================
# REGISTER NODES
# ==========================================

workflow.add_node(
    "research",
    research_node
)

workflow.add_node(
    "planner",
    planner_node
)

workflow.add_node(
    "critic",
    critic_node
)

workflow.add_node(
    "optimizer",
    optimizer_node
)

# ==========================================
# ENTRY POINT
# ==========================================

workflow.set_entry_point(
    "research"
)

# ==========================================
# GRAPH EDGES
# ==========================================

workflow.add_edge(
    "research",
    "planner"
)

workflow.add_edge(
    "planner",
    "critic"
)

# ==========================================
# CONDITIONAL ROUTING
# ==========================================

workflow.add_conditional_edges(
    "critic",
    reflection_router,
    {
        "planner_retry": "planner",
        "optimizer": "optimizer"
    }
)

# ==========================================
# FINAL EDGE
# ==========================================

workflow.add_edge(
    "optimizer",
    END
)

# ==========================================
# COMPILE GRAPH
# ==========================================

cognitive_graph = workflow.compile()