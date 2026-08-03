import logging
from typing import Any, Dict

from fastapi import APIRouter, FastAPI

log = logging.getLogger(__name__)

# ==============================================================
# API VERSIONING SCHEME
#
# All routes are registered under /api/ (unversioned) for
# backward compatibility. New routes SHOULD be registered under
# /api/v1/ by including them in a versioned APIRouter.
#
# Migration pattern:
#   1. Create router with prefix="/api/v1/<resource>"
#   2. Register both unversioned and versioned for one release
#   3. Announce deprecation in CHANGELOG
#   4. Remove unversioned path in next major release
# Future v2 routes go to /api/v2/ in a separate router group.
# ==============================================================

_v1_router = APIRouter(prefix="/api/v1")


@_v1_router.get("/health")
async def v1_health():
    return {"version": "v1", "status": "healthy"}


def register_all_routers(app: FastAPI) -> Dict[str, bool]:
    availability: Dict[str, bool] = {}

    # Versioned routes
    app.include_router(_v1_router)

    from backend.websocket.websocket_router import router as websocket_router
    app.include_router(websocket_router)

    # NOTE: registered before `backend.mission.routes` below on purpose —
    # that router defines a catch-all GET /api/missions/{mission_id}, and
    # FastAPI matches routes in registration order. If the generic route
    # registers first, requests to the literal /active and /completed
    # paths here get shadowed and 422 on UUID-parsing "active"/"completed".
    try:
        from backend.api.routes.mission_routes import router as advanced_mission_router
        from backend.api.routes.orchestrator_routes import router as orchestrator_router
        app.include_router(advanced_mission_router, prefix="/api/missions", tags=["Missions"])
        app.include_router(orchestrator_router, prefix="/api/orchestrator", tags=["Orchestrator"])
        availability["advanced_api"] = True
    except Exception:
        _advanced_fallback = APIRouter()

        @_advanced_fallback.get("/api/missions/active")
        async def get_active_missions_fallback():
            return {"missions": [], "status": "degraded", "detail": "Advanced mission runtime unavailable"}

        @_advanced_fallback.get("/api/missions/completed")
        async def get_completed_missions_fallback():
            return {"missions": [], "status": "degraded", "detail": "Advanced mission runtime unavailable"}

        @_advanced_fallback.get("/api/orchestrator/loops/active")
        async def get_active_loops_fallback():
            return {"loops": [], "status": "degraded", "detail": "Orchestrator loop runtime unavailable"}

        @_advanced_fallback.post("/api/orchestrator/autonomous")
        async def autonomous_execution_fallback(payload: Dict[str, Any]):
            return {"status": "degraded", "accepted": False, "detail": "Autonomous execution unavailable", "payload_received": payload}

        app.include_router(_advanced_fallback)
        availability["advanced_api"] = False

    try:
        from backend.mission.routes import router as mission_router
        app.include_router(mission_router)
        availability["mission"] = True
    except Exception as _m_err:
        log.warning("Mission routes unavailable: %s", _m_err)
        availability["mission"] = False

    try:
        from backend.api.auth_routes import router as auth_router
        app.include_router(auth_router)
        availability["auth"] = True
    except Exception as _auth_err:
        availability["auth"] = False
        log.warning(f"Auth routes unavailable: {_auth_err}")

    try:
        from backend.api.tenant_routes import router as tenant_router
        app.include_router(tenant_router)
        availability["tenant"] = True
    except Exception as _tenant_err:
        availability["tenant"] = False
        log.warning(f"Tenant routes unavailable: {_tenant_err}")

    # Governance Runtime routes (Phase 6A)
    try:
        from backend.governance.routes import router as governance_router
        app.include_router(governance_router)
        availability["governance_runtime"] = True
        log.info("Governance Runtime routes registered at /api/governance")
    except Exception as _gov_err:
        _gov_detail = str(_gov_err)
        _gov_fallback = APIRouter()
        @_gov_fallback.get("/api/governance/health")
        async def governance_health_fallback():
            return {"status": "unavailable", "detail": _gov_detail}
        app.include_router(_gov_fallback)
        availability["governance_runtime"] = False
        log.warning(f"Governance Runtime routes unavailable: {_gov_detail}")

    # Knowledge Runtime routes (Phase 7A)
    try:
        from backend.knowledge.routes import router as knowledge_router
        app.include_router(knowledge_router)
        availability["knowledge_runtime"] = True
        log.info("Knowledge Runtime routes registered at /api/knowledge")
    except Exception as _k_err:
        _k_detail = str(_k_err)
        _k_fallback = APIRouter()

        @_k_fallback.get("/api/knowledge/health")
        async def knowledge_health_fallback():
            return {"status": "unavailable", "detail": _k_detail}

        app.include_router(_k_fallback)
        availability["knowledge_runtime"] = False
        log.warning(f"Knowledge Runtime routes unavailable: {_k_detail}")

    # Learning Runtime routes (Phase 8A)
    try:
        from backend.learning.routes import router as learning_router
        app.include_router(learning_router)
        availability["learning_runtime"] = True
        log.info("Learning Runtime routes registered at /api/learning")
    except Exception as _lrn_err:
        _lrn_detail = str(_lrn_err)
        _lrn_fallback = APIRouter()

        @_lrn_fallback.get("/api/learning/health")
        async def learning_health_fallback():
            return {"status": "unavailable", "detail": _lrn_detail}

        app.include_router(_lrn_fallback)
        availability["learning_runtime"] = False
        log.warning(f"Learning Runtime routes unavailable: {_lrn_detail}")

    # AI Runtime routes (Phase 9A)
    try:
        from backend.ai.routes import router as ai_router
        app.include_router(ai_router)
        availability["ai_runtime"] = True
        log.info("AI Runtime routes registered at /api/ai")
    except Exception as _ai_err:
        _ai_detail = str(_ai_err)
        _ai_fallback = APIRouter()

        @_ai_fallback.get("/api/ai/health")
        async def ai_health_fallback():
            return {"status": "unavailable", "detail": _ai_detail}

        app.include_router(_ai_fallback)
        availability["ai_runtime"] = False
        log.warning(f"AI Runtime routes unavailable: {_ai_detail}")

    # LLM Provider Runtime routes (Phase 10A)
    try:
        from backend.llm_provider.routes import router as llm_provider_router
        app.include_router(llm_provider_router)
        availability["llm_provider"] = True
        log.info("LLM Provider Runtime routes registered at /api/llm")
    except Exception as _llm_err:
        _llm_detail = str(_llm_err)
        _llm_fallback = APIRouter()

        @_llm_fallback.get("/api/llm/providers")
        async def llm_providers_fallback():
            return {"providers": [], "detail": _llm_detail}

        app.include_router(_llm_fallback)
        availability["llm_provider"] = False
        log.warning(f"LLM Provider Runtime routes unavailable: {_llm_detail}")

    # Execution Runtime routes (Phase 4)
    try:
        from backend.execution.routes import router as execution_router
        app.include_router(execution_router)
        availability["execution"] = True
    except Exception as _exec_err:
        availability["execution"] = False
        log.warning(f"Execution routes unavailable: {_exec_err}")

    try:
        from backend.api.mission_execution_routes import router as mission_execution_router
        app.include_router(mission_execution_router, tags=["Mission Execution"])
        availability["mission_execution"] = True
    except Exception as _me_err:
        availability["mission_execution"] = False
        log.warning(f"Mission execution routes unavailable: {_me_err}")

    try:
        from backend.api.runtime_api import router as runtime_api_router
        app.include_router(runtime_api_router)
        availability["runtime_api"] = True
    except Exception as _runtime_api_err:
        availability["runtime_api"] = False
        log.warning(f"Runtime API unavailable: {_runtime_api_err}")

    try:
        from backend.api.memory_routes import router as memory_router
        app.include_router(memory_router)
        availability["memory"] = True
    except Exception:
        _mem_fallback = APIRouter()

        @_mem_fallback.get("/api/memory/status")
        async def memory_status_fallback():
            return {"status": "unavailable", "detail": "Memory layer failed to load"}

        app.include_router(_mem_fallback)
        availability["memory"] = False

    try:
        from backend.api.memory_explorer_routes import router as _memory_explorer_router
        app.include_router(_memory_explorer_router, prefix="/api")
        log.info("Memory Explorer routes registered at /api/memory/explorer")
        availability["memory_explorer"] = True
    except Exception as _mexpl_err:
        _mexpl_fallback = APIRouter()

        @_mexpl_fallback.get("/api/memory/explorer/health")
        async def memory_explorer_health_fallback():
            return {"status": "unavailable", "detail": "Memory Explorer routes failed to initialise"}

        app.include_router(_mexpl_fallback)
        availability["memory_explorer"] = False
        log.warning(f"Memory Explorer routes unavailable: {_mexpl_err}")

    try:
        from backend.api.governance_center_routes import router as _gov_center_router
        app.include_router(_gov_center_router, prefix="/api")
        log.info("Governance Center routes registered at /api/governance-center")
        availability["governance_center"] = True
    except Exception as _gc_err:
        _gc_fallback = APIRouter()

        @_gc_fallback.get("/api/governance-center/health")
        async def governance_center_health_fallback():
            return {"status": "unavailable", "detail": "Governance Center routes failed to initialise"}

        app.include_router(_gc_fallback)
        availability["governance_center"] = False

    try:
        from backend.api.executive_routes import router as _executive_router
        app.include_router(_executive_router, prefix="/api")
        log.info("Executive routes registered at /api/executive")
        availability["executive"] = True
    except Exception as _exec_err:
        _exec_fallback = APIRouter()

        @_exec_fallback.get("/api/executive/health")
        async def executive_health_fallback():
            return {"status": "unavailable", "detail": "Executive routes failed to initialise"}

        app.include_router(_exec_fallback)
        availability["executive"] = False

    try:
        from backend.api.vector_search_routes import router as vector_search_router
        app.include_router(vector_search_router)
        availability["vector_search"] = True
    except Exception as _vector_search_err:
        _vec_fallback = APIRouter()

        @_vec_fallback.get("/api/vector/health")
        async def vector_health_fallback():
            return {"status": "unavailable", "pgvector": False, "detail": "Vector search layer failed to initialise"}

        app.include_router(_vec_fallback)
        availability["vector_search"] = False
        log.warning(f"Vector search routes unavailable: {_vector_search_err}")

    try:
        from backend.api.rabbitmq_routes import router as _rabbitmq_router
        app.include_router(_rabbitmq_router)
        availability["rabbitmq"] = True
    except Exception as _rmq_err:
        _rmq_fallback = APIRouter()

        @_rmq_fallback.get("/api/rabbitmq/health")
        async def rabbitmq_health_fallback():
            return {"status": "unavailable", "detail": "RabbitMQ routes failed to initialise"}

        app.include_router(_rmq_fallback)
        availability["rabbitmq"] = False
        log.warning(f"RabbitMQ routes unavailable: {_rmq_err}")

    try:
        from backend.api.graph_routes import graph_router as _graph_router
        app.include_router(_graph_router)
        availability["graph"] = True
    except Exception as _graph_err:
        _graph_fallback = APIRouter()

        @_graph_fallback.get("/api/graph/health")
        async def graph_health_fallback():
            return {"status": "unavailable", "detail": "Graph routes failed to initialise"}

        app.include_router(_graph_fallback)
        availability["graph"] = False
        log.warning(f"Graph routes unavailable: {_graph_err}")

    try:
        from backend.api.mission_replay_routes import router as _replay_router
        app.include_router(_replay_router, prefix="/api")
        log.info("Mission Replay routes registered at /api/mission-replay")
        availability["mission_replay"] = True
    except Exception as _replay_err:
        _replay_fallback = APIRouter()

        @_replay_fallback.get("/api/mission-replay/health")
        async def replay_health_fallback():
            return {"status": "unavailable", "detail": "Mission replay routes failed to initialise"}

        app.include_router(_replay_fallback)
        availability["mission_replay"] = False
        log.warning(f"Mission replay routes unavailable: {_replay_err}")

    try:
        from backend.api.enterprise_replay_routes import router as _enterprise_replay_router
        app.include_router(_enterprise_replay_router)
        log.info("Enterprise Replay routes registered at /api/enterprise-replay")
        availability["enterprise_replay"] = True
    except Exception as _enterprise_replay_err:
        _enterprise_replay_fallback = APIRouter()

        @_enterprise_replay_fallback.get("/api/enterprise-replay/health")
        async def enterprise_replay_health_fallback():
            return {"status": "unavailable", "detail": "Enterprise replay routes failed to initialise"}

        app.include_router(_enterprise_replay_fallback)
        availability["enterprise_replay"] = False
        log.warning(f"Enterprise replay routes unavailable: {_enterprise_replay_err}")

    try:
        from backend.api.retention_routes import router as _retention_router
        app.include_router(_retention_router)
        log.info("Retention routes registered at /api/admin/retention")
        availability["retention"] = True
    except Exception as _retention_err:
        _retention_fallback = APIRouter()

        @_retention_fallback.get("/api/admin/retention/health")
        async def retention_health_fallback():
            return {"status": "unavailable", "detail": "Retention routes failed to initialise"}

        app.include_router(_retention_fallback)
        availability["retention"] = False
        log.warning(f"Retention routes unavailable: {_retention_err}")

    try:
        from backend.api.admin_routes import router as _admin_router
        app.include_router(_admin_router)
        log.info("Admin routes registered at /api/admin")
        availability["admin"] = True
    except Exception as _admin_err:
        _admin_fallback = APIRouter()

        @_admin_fallback.get("/api/admin/health")
        async def admin_health_fallback():
            return {"status": "unavailable", "detail": "Admin routes failed to initialise"}

        app.include_router(_admin_fallback)
        availability["admin"] = False
        log.warning(f"Admin routes unavailable: {_admin_err}")

    try:
        from backend.api.telemetry_routes import router as telemetry_router
        app.include_router(telemetry_router)
        availability["telemetry"] = True
    except Exception as _tel_err:
        availability["telemetry"] = False
        log.warning(f"Telemetry routes unavailable: {_tel_err}")

    try:
        from backend.api.mission_library_routes import router as mission_library_router
        app.include_router(mission_library_router)
        log.info("Mission Library routes registered at /api/mission-library")
        availability["mission_library"] = True
    except Exception as _ml_err:
        _ml_err_detail = str(_ml_err)
        _ml_fallback = APIRouter()

        @_ml_fallback.get("/api/mission-library/missions")
        async def mission_library_health_fallback():
            return {"missions": [], "total": 0, "status": "unavailable", "detail": _ml_err_detail}

        app.include_router(_ml_fallback)
        availability["mission_library"] = False
        log.warning(f"Mission Library routes unavailable: {_ml_err_detail}")

    try:
        from backend.api.approval_center_routes import router as approval_center_router
        app.include_router(approval_center_router)
        log.info("Approval Center routes registered at /api/approval-center")
        availability["approval_center"] = True
    except Exception as _ac_err:
        _ac_err_detail = str(_ac_err)
        _ac_fallback = APIRouter()

        @_ac_fallback.get("/api/approval-center/policies")
        async def approval_center_health_fallback():
            return {"policies": [], "status": "unavailable", "detail": _ac_err_detail}

        app.include_router(_ac_fallback)
        availability["approval_center"] = False
        log.warning(f"Approval Center routes unavailable: {_ac_err_detail}")

    try:
        from backend.api.security_center_routes import router as security_center_router
        app.include_router(security_center_router)
        log.info("Security Center routes registered at /api/security")
        availability["security_center"] = True
    except Exception as _sc_err:
        _sc_err_detail = str(_sc_err)
        _sc_fallback = APIRouter()

        @_sc_fallback.get("/api/security/status")
        async def security_center_health_fallback():
            return {"status": "unavailable", "detail": _sc_err_detail}

        app.include_router(_sc_fallback)
        availability["security_center"] = False
        log.warning(f"Security Center routes unavailable: {_sc_err_detail}")

    try:
        from backend.api.governance_routes import router as governance_router
        app.include_router(governance_router)
        log.info("Governance routes registered")
        availability["governance"] = True
    except Exception as _gov_err:
        _gov_err_detail = str(_gov_err)
        _gov_fallback = APIRouter()

        @_gov_fallback.get("/governance/health")
        async def governance_health_fallback():
            return {"status": "unavailable", "detail": _gov_err_detail}

        @_gov_fallback.get("/governance/queue")
        async def governance_queue_fallback():
            return {"requests": [], "total": 0, "detail": _gov_err_detail}

        @_gov_fallback.get("/governance/audit")
        async def governance_audit_fallback():
            return {"entries": [], "total": 0, "detail": _gov_err_detail}

        app.include_router(_gov_fallback)
        availability["governance"] = False
        log.warning(f"Governance routes unavailable: {_gov_err_detail}")

    try:
        from backend.api.enterprise_mission_routes import router as enterprise_mission_router
        app.include_router(enterprise_mission_router)
        log.info("Enterprise Mission routes registered at /api/enterprise/missions")
        availability["enterprise_mission"] = True
    except Exception as _em_err:
        _em_err_detail = str(_em_err)
        _em_fallback = APIRouter()

        @_em_fallback.get("/api/enterprise/missions/templates")
        async def enterprise_mission_templates_fallback():
            return {"templates": [], "total": 0, "detail": _em_err_detail}

        @_em_fallback.post("/api/enterprise/missions/launch")
        async def enterprise_mission_launch_fallback():
            return {"status": "unavailable", "detail": _em_err_detail}

        app.include_router(_em_fallback)
        availability["enterprise_mission"] = False
        log.warning(f"Enterprise Mission routes unavailable: {_em_err_detail}")

    try:
        from backend.api.enterprise_knowledge_routes import router as enterprise_knowledge_router
        app.include_router(enterprise_knowledge_router)
        log.info("Enterprise Knowledge routes registered at /api/enterprise/search and /api/enterprise/graph/*")
        availability["enterprise_knowledge"] = True
    except Exception as _ek_err:
        _ek_err_detail = str(_ek_err)
        _ek_fallback = APIRouter()

        @_ek_fallback.get("/api/enterprise/search")
        async def enterprise_search_fallback():
            return {"results": [], "total": 0, "detail": _ek_err_detail}

        @_ek_fallback.get("/api/enterprise/knowledge/health")
        async def enterprise_knowledge_health_fallback():
            return {"status": "unavailable", "detail": _ek_err_detail}

        app.include_router(_ek_fallback)
        availability["enterprise_knowledge"] = False
        log.warning(f"Enterprise Knowledge routes unavailable: {_ek_err_detail}")

    try:
        from backend.api.enterprise_learning_routes import router as enterprise_learning_router
        app.include_router(enterprise_learning_router)
        log.info("Enterprise Learning routes registered at /api/enterprise/learning/*")
        availability["enterprise_learning"] = True
    except Exception as _el_err:
        _el_err_detail = str(_el_err)
        _el_fallback = APIRouter()

        @_el_fallback.get("/api/enterprise/learning/lessons")
        async def enterprise_learning_lessons_fallback():
            return {"lessons": [], "total": 0, "detail": _el_err_detail}

        @_el_fallback.get("/api/enterprise/learning/dashboard")
        async def enterprise_learning_dashboard_fallback():
            return {"summary": {}, "detail": _el_err_detail}

        app.include_router(_el_fallback)
        availability["enterprise_learning"] = False
        log.warning(f"Enterprise Learning routes unavailable: {_el_err_detail}")

    try:
        from backend.api.enterprise_monitoring_routes import router as enterprise_monitoring_router
        app.include_router(enterprise_monitoring_router)
        log.info("Enterprise Monitoring routes registered at /api/monitoring/*")
        availability["enterprise_monitoring"] = True
    except Exception as _em_err:
        _em_err_detail = str(_em_err)
        _em_fallback = APIRouter()

        @_em_fallback.get("/api/monitoring/health")
        async def monitoring_health_fallback():
            return {"status": "unavailable", "detail": _em_err_detail}

        @_em_fallback.get("/api/monitoring/watchers")
        async def monitoring_watchers_fallback():
            return {"watchers": [], "total": 0, "detail": _em_err_detail}

        app.include_router(_em_fallback)
        availability["enterprise_monitoring"] = False
        log.warning(f"Enterprise Monitoring routes unavailable: {_em_err_detail}")

    try:
        from backend.api.enterprise_recommendation_routes import router as enterprise_recommendation_router
        app.include_router(enterprise_recommendation_router)
        log.info("Enterprise Recommendation routes registered at /api/recommendations/*")
        availability["enterprise_recommendation"] = True
    except Exception as _erec_err:
        _erec_err_detail = str(_erec_err)
        _erec_fallback = APIRouter()

        @_erec_fallback.get("/api/recommendations/health")
        async def recommendation_health_fallback():
            return {"status": "unavailable", "detail": _erec_err_detail}

        app.include_router(_erec_fallback)
        availability["enterprise_recommendation"] = False
        log.warning(f"Enterprise Recommendation routes unavailable: {_erec_err_detail}")

    try:
        from backend.api.enterprise_engineering_routes import router as enterprise_engineering_router
        app.include_router(enterprise_engineering_router)
        log.info("Enterprise Engineering routes registered at /api/engineering/*")
        availability["enterprise_engineering"] = True
    except Exception as _eeng_err:
        _eeng_err_detail = str(_eeng_err)
        _eeng_fallback = APIRouter()

        @_eeng_fallback.get("/api/engineering/agents")
        async def engineering_health_fallback():
            return {"agents": [], "total": 0, "status": "unavailable", "detail": _eeng_err_detail}

        app.include_router(_eeng_fallback)
        availability["enterprise_engineering"] = False
        log.warning(f"Enterprise Engineering routes unavailable: {_eeng_err_detail}")

    try:
        from backend.api.enterprise_decision_routes import router as enterprise_decision_router
        app.include_router(enterprise_decision_router)
        log.info("Enterprise Engineering Decision routes registered at /api/engineering/decision/*")
        availability["enterprise_decision"] = True
    except Exception as _edec_err:
        _edec_err_detail = str(_edec_err)
        _edec_fallback = APIRouter()

        @_edec_fallback.post("/api/engineering/decision/analyze")
        async def decision_analyze_fallback():
            return {"status": "unavailable", "detail": _edec_err_detail}

        @_edec_fallback.get("/api/engineering/decision/history")
        async def decision_history_fallback():
            return {"executions": [], "total": 0, "detail": _edec_err_detail}

        app.include_router(_edec_fallback)
        availability["enterprise_decision"] = False
        log.warning(f"Enterprise Engineering Decision routes unavailable: {_edec_err_detail}")

    try:
        from backend.api.enterprise_context_routes import router as enterprise_context_router
        app.include_router(enterprise_context_router)
        log.info("Enterprise Engineering Context routes registered at /api/engineering/context/*")
        availability["enterprise_context"] = True
    except Exception as _ectx_err:
        _ectx_err_detail = str(_ectx_err)
        _ectx_fallback = APIRouter()

        @_ectx_fallback.get("/api/engineering/context/health")
        async def context_health_fallback():
            return {"status": "unavailable", "detail": _ectx_err_detail}

        app.include_router(_ectx_fallback)
        availability["enterprise_context"] = False
        log.warning(f"Enterprise Engineering Context routes unavailable: {_ectx_err_detail}")

    try:
        from backend.api.enterprise_memory_routes import router as enterprise_memory_router
        app.include_router(enterprise_memory_router)
        log.info("Enterprise Engineering Memory routes registered at /api/engineering/memory/*")
        availability["enterprise_memory"] = True
    except Exception as _emem_err:
        _emem_err_detail = str(_emem_err)
        _emem_fallback = APIRouter()

        @_emem_fallback.get("/api/engineering/memory/experiences")
        async def memory_experiences_fallback():
            return {"experiences": [], "total": 0, "detail": _emem_err_detail}

        app.include_router(_emem_fallback)
        availability["enterprise_memory"] = False
        log.warning(f"Enterprise Engineering Memory routes unavailable: {_emem_err_detail}")

    try:
        from backend.api.enterprise_simulation_routes import router as enterprise_simulation_router
        app.include_router(enterprise_simulation_router)
        log.info("Enterprise Predictive Simulation routes registered at /api/engineering/simulation/*")
        availability["enterprise_simulation"] = True
    except Exception as _esim_err:
        _esim_err_detail = str(_esim_err)
        _esim_fallback = APIRouter()

        @_esim_fallback.get("/api/engineering/simulation/predictions")
        async def simulation_predictions_fallback():
            return {"predictions": [], "detail": _esim_err_detail}

        app.include_router(_esim_fallback)
        availability["enterprise_simulation"] = False
        log.warning(f"Enterprise Predictive Simulation routes unavailable: {_esim_err_detail}")

    try:
        from backend.api.enterprise_verification_routes import router as enterprise_verification_router
        app.include_router(enterprise_verification_router)
        log.info("Enterprise Verification Intelligence routes registered at /api/engineering/verification/*")
        availability["enterprise_verification"] = True
    except Exception as _ever_err:
        _ever_err_detail = str(_ever_err)
        _ever_fallback = APIRouter()

        @_ever_fallback.get("/api/engineering/verification/list")
        async def verification_list_fallback():
            return {"verifications": [], "detail": _ever_err_detail}

        app.include_router(_ever_fallback)
        availability["enterprise_verification"] = False
        log.warning(f"Enterprise Verification Intelligence routes unavailable: {_ever_err_detail}")

    try:
        from backend.api.enterprise_executive_routes import router as enterprise_executive_routes_router
        app.include_router(enterprise_executive_routes_router)
        log.info("Enterprise Executive Runtime routes registered at /api/engineering/executive/*")
        availability["enterprise_executive"] = True
    except Exception as _eexec_err:
        _eexec_err_detail = str(_eexec_err)
        _eexec_fallback = APIRouter()

        @_eexec_fallback.get("/api/engineering/executive/missions")
        async def executive_missions_fallback():
            return {"missions": [], "detail": _eexec_err_detail}

        app.include_router(_eexec_fallback)
        availability["enterprise_executive"] = False
        log.warning(f"Enterprise Executive Runtime routes unavailable: {_eexec_err_detail}")

    try:
        from backend.api.enterprise_explainability_routes import router as enterprise_explainability_router
        app.include_router(enterprise_explainability_router)
        log.info("Enterprise Explainability routes registered at /api/explainability/*")
        availability["enterprise_explainability"] = True
    except Exception as _eexp_err:
        _eexp_err_detail = str(_eexp_err)
        _eexp_fallback = APIRouter()

        @_eexp_fallback.get("/api/explainability/missions")
        async def explainability_missions_fallback():
            return {"missions": [], "total": 0, "detail": _eexp_err_detail}

        @_eexp_fallback.get("/api/explainability/dashboard")
        async def explainability_dashboard_fallback():
            return {"detail": _eexp_err_detail}

        app.include_router(_eexp_fallback)
        availability["enterprise_explainability"] = False
        log.warning(f"Enterprise Explainability routes unavailable: {_eexp_err_detail}")

    try:
        from backend.api.enterprise_governance_routes import router as enterprise_governance_router
        app.include_router(enterprise_governance_router)
        log.info("Enterprise Governance routes registered at /api/governance/*")
        availability["enterprise_governance"] = True
    except Exception as _egov_err:
        _egov_err_detail = str(_egov_err)
        _egov_fallback = APIRouter()

        @_egov_fallback.get("/api/governance/policies")
        async def governance_policies_fallback():
            return {"policies": [], "total": 0, "detail": _egov_err_detail}

        app.include_router(_egov_fallback)
        availability["enterprise_governance"] = False
        log.warning(f"Enterprise Governance routes unavailable: {_egov_err_detail}")

    try:
        from backend.api.enterprise_analytics_routes import router as enterprise_analytics_router
        app.include_router(enterprise_analytics_router)
        log.info("Enterprise Analytics routes registered at /api/analytics/*")
        availability["enterprise_analytics"] = True
    except Exception as _eana_err:
        _eana_err_detail = str(_eana_err)
        _eana_fallback = APIRouter()

        @_eana_fallback.get("/api/analytics/metrics")
        async def analytics_metrics_fallback():
            return {"metrics": [], "total": 0, "detail": _eana_err_detail}

        app.include_router(_eana_fallback)
        availability["enterprise_analytics"] = False
        log.warning(f"Enterprise Analytics routes unavailable: {_eana_err_detail}")

    try:
        from backend.api.enterprise_delivery_routes import router as enterprise_delivery_router
        app.include_router(enterprise_delivery_router)
        log.info("Enterprise Delivery routes registered at /api/delivery")
        availability["enterprise_delivery"] = True
    except Exception as _edel_err:
        _edel_err_detail = str(_edel_err)
        _edel_fallback = APIRouter()

        @_edel_fallback.get("/api/delivery")
        async def delivery_fallback_list():
            return {"deliveries": [], "error": _edel_err_detail}

        app.include_router(_edel_fallback)
        availability["enterprise_delivery"] = False
        log.warning(f"Enterprise Delivery routes unavailable: {_edel_err_detail}")

    try:
        from backend.api.autonomous_trigger_routes import router as autonomous_trigger_router
        app.include_router(autonomous_trigger_router)
        log.info("Autonomous Trigger routes registered at /api/triggers")
        availability["autonomous_trigger"] = True
    except Exception as _atrig_err:
        _atrig_err_detail = str(_atrig_err)
        _atrig_fallback = APIRouter()

        @_atrig_fallback.get("/api/triggers")
        async def trigger_fallback_list():
            return {"policies": [], "error": _atrig_err_detail}

        app.include_router(_atrig_fallback)
        availability["autonomous_trigger"] = False
        log.warning(f"Autonomous Trigger routes unavailable: {_atrig_err_detail}")

    try:
        from backend.api.enterprise_sandbox_routes import router as enterprise_sandbox_router
        app.include_router(enterprise_sandbox_router)
        log.info("Enterprise Execution Sandbox routes registered at /api/sandboxes")
        availability["enterprise_sandbox"] = True
    except Exception as _esbx_err:
        _esbx_err_detail = str(_esbx_err)
        _esbx_fallback = APIRouter()

        @_esbx_fallback.get("/api/sandboxes")
        async def sandbox_fallback_list():
            return {"sandboxes": [], "error": _esbx_err_detail}

        app.include_router(_esbx_fallback)
        availability["enterprise_sandbox"] = False
        log.warning(f"Enterprise Sandbox routes unavailable: {_esbx_err_detail}")

    try:
        from backend.api.enterprise_code_routes import router as enterprise_code_router
        app.include_router(enterprise_code_router)
        log.info("Enterprise Code Intelligence routes registered at /api/code")
        availability["enterprise_code"] = True
    except Exception as _ecode_err:
        _ecode_err_detail = str(_ecode_err)
        _ecode_fallback = APIRouter()

        @_ecode_fallback.get("/api/code/repositories")
        async def code_fallback_repos():
            return {"repositories": [], "error": _ecode_err_detail}

        app.include_router(_ecode_fallback)
        availability["enterprise_code"] = False
        log.warning(f"Enterprise Code Intelligence routes unavailable: {_ecode_err_detail}")

    try:
        from backend.api.enterprise_patch_routes import router as enterprise_patch_router
        app.include_router(enterprise_patch_router)
        log.info("Enterprise Patch Pipeline routes registered at /api/patches")
        availability["enterprise_patch"] = True
    except Exception as _epatch_err:
        _epatch_err_detail = str(_epatch_err)
        _epatch_fallback = APIRouter()

        @_epatch_fallback.get("/api/patches/plans")
        async def patch_fallback_plans():
            return {"plans": [], "error": _epatch_err_detail}

        app.include_router(_epatch_fallback)
        availability["enterprise_patch"] = False
        log.warning(f"Enterprise Patch Pipeline routes unavailable: {_epatch_err_detail}")

    try:
        from backend.api.enterprise_git_routes import router as enterprise_git_router
        app.include_router(enterprise_git_router)
        log.info("Enterprise Git Operations routes registered at /api/git")
        availability["enterprise_git"] = True
    except Exception as _egit_err:
        _egit_err_detail = str(_egit_err)
        _egit_fallback = APIRouter()

        @_egit_fallback.get("/api/git/branches")
        async def git_fallback_branches():
            return {"branches": [], "error": _egit_err_detail}

        app.include_router(_egit_fallback)
        availability["enterprise_git"] = False
        log.warning(f"Enterprise Git Operations routes unavailable: {_egit_err_detail}")

    try:
        from backend.api.enterprise_github_routes import router as enterprise_github_router
        app.include_router(enterprise_github_router)
        log.info("Enterprise GitHub Integration routes registered at /api/github")
        availability["enterprise_github"] = True
    except Exception as _egh_err:
        _egh_err_detail = str(_egh_err)
        _egh_fallback = APIRouter()

        @_egh_fallback.get("/api/github/dashboard")
        async def github_fallback_dashboard():
            return {"total_webhooks": 0, "error": _egh_err_detail}

        app.include_router(_egh_fallback)
        availability["enterprise_github"] = False
        log.warning(f"Enterprise GitHub Integration routes unavailable: {_egh_err_detail}")

    try:
        from backend.api.enterprise_gitlab_routes import router as enterprise_gitlab_router
        app.include_router(enterprise_gitlab_router)
        log.info("Enterprise GitLab Integration routes registered at /api/gitlab")
        availability["enterprise_gitlab"] = True
    except Exception as _egl_err:
        availability["enterprise_gitlab"] = False
        log.warning(f"Enterprise GitLab Integration routes unavailable: {_egl_err}")

    try:
        from backend.api.enterprise_flaky_tests_routes import router as enterprise_flaky_tests_router
        app.include_router(enterprise_flaky_tests_router)
        log.info("Enterprise Flaky Test Detection routes registered at /api/flaky-tests")
        availability["enterprise_flaky_tests"] = True
    except Exception as _eft_err:
        availability["enterprise_flaky_tests"] = False
        log.warning(f"Enterprise Flaky Test Detection routes unavailable: {_eft_err}")

    try:
        from backend.api.enterprise_rollbacks_routes import router as enterprise_rollbacks_router
        app.include_router(enterprise_rollbacks_router)
        log.info("Enterprise Deploy Rollback Automation routes registered at /api/rollbacks")
        availability["enterprise_rollbacks"] = True
    except Exception as _erb_err:
        availability["enterprise_rollbacks"] = False
        log.warning(f"Enterprise Deploy Rollback Automation routes unavailable: {_erb_err}")

    try:
        from backend.api.enterprise_incidents_routes import router as enterprise_incidents_router
        app.include_router(enterprise_incidents_router)
        log.info("Enterprise Alert Incident Correlation routes registered at /api/incidents")
        availability["enterprise_incidents"] = True
    except Exception as _einc_err:
        availability["enterprise_incidents"] = False
        log.warning(f"Enterprise Alert Incident Correlation routes unavailable: {_einc_err}")

    try:
        from backend.api.enterprise_credentials_routes import router as enterprise_credentials_router
        app.include_router(enterprise_credentials_router)
        log.info("Enterprise Credential Monitoring routes registered at /api/credentials")
        availability["enterprise_credentials"] = True
    except Exception as _ecred_err:
        availability["enterprise_credentials"] = False
        log.warning(f"Enterprise Credential Monitoring routes unavailable: {_ecred_err}")

    try:
        from backend.api.enterprise_vulnerabilities_routes import router as enterprise_vulnerabilities_router
        app.include_router(enterprise_vulnerabilities_router)
        log.info("Enterprise Vulnerability Monitoring routes registered at /api/vulnerabilities")
        availability["enterprise_vulnerabilities"] = True
    except Exception as _evuln_err:
        availability["enterprise_vulnerabilities"] = False
        log.warning(f"Enterprise Vulnerability Monitoring routes unavailable: {_evuln_err}")

    try:
        from backend.api.enterprise_branch_protection_routes import router as enterprise_branch_protection_router
        app.include_router(enterprise_branch_protection_router)
        log.info("Enterprise Branch Protection Monitoring routes registered at /api/branch-protection")
        availability["enterprise_branch_protection"] = True
    except Exception as _ebp_err:
        availability["enterprise_branch_protection"] = False
        log.warning(f"Enterprise Branch Protection Monitoring routes unavailable: {_ebp_err}")

    try:
        from backend.api.enterprise_docker_health_routes import router as enterprise_docker_health_router
        app.include_router(enterprise_docker_health_router)
        log.info("Enterprise Docker Health Monitoring routes registered at /api/docker-health")
        availability["enterprise_docker_health"] = True
    except Exception as _edh_err:
        availability["enterprise_docker_health"] = False
        log.warning(f"Enterprise Docker Health Monitoring routes unavailable: {_edh_err}")

    try:
        from backend.api.enterprise_cost_anomaly_routes import router as enterprise_cost_anomaly_router
        app.include_router(enterprise_cost_anomaly_router)
        log.info("Enterprise Cost Anomaly Monitoring routes registered at /api/cost-anomaly")
        availability["enterprise_cost_anomaly"] = True
    except Exception as _eca_err:
        availability["enterprise_cost_anomaly"] = False
        log.warning(f"Enterprise Cost Anomaly Monitoring routes unavailable: {_eca_err}")

    try:
        from backend.api.enterprise_cicd_routes import router as enterprise_cicd_router
        app.include_router(enterprise_cicd_router)
        log.info("Enterprise CI/CD Intelligence routes registered at /api/cicd")
        availability["enterprise_cicd"] = True
    except Exception as _ecicd_err:
        _ecicd_err_detail = str(_ecicd_err)
        _ecicd_fallback = APIRouter()

        @_ecicd_fallback.get("/api/cicd/dashboard")
        async def cicd_fallback_dashboard():
            return {"total_builds": 0, "error": _ecicd_err_detail}

        app.include_router(_ecicd_fallback)
        availability["enterprise_cicd"] = False
        log.warning(f"Enterprise CI/CD Intelligence routes unavailable: {_ecicd_err_detail}")

    try:
        from backend.api.enterprise_infrastructure_routes import router as enterprise_infra_router
        app.include_router(enterprise_infra_router)
        log.info("Enterprise Infrastructure Intelligence routes registered at /api/infrastructure")
        availability["enterprise_infrastructure"] = True
    except Exception as _einfra_err:
        _einfra_err_detail = str(_einfra_err)
        _einfra_fallback = APIRouter()

        @_einfra_fallback.get("/api/infrastructure/dashboard")
        async def infra_fallback_dashboard():
            return {"clusters": {"total": 0}, "error": _einfra_err_detail}

        app.include_router(_einfra_fallback)
        availability["enterprise_infrastructure"] = False
        log.warning(f"Enterprise Infrastructure Intelligence routes unavailable: {_einfra_err_detail}")

    try:
        from backend.api.enterprise_root_cause_routes import router as enterprise_rca_router
        app.include_router(enterprise_rca_router)
        log.info("Enterprise Root Cause Analysis routes registered at /api/rca")
        availability["enterprise_rca"] = True
    except Exception as _erca_err:
        _erca_err_detail = str(_erca_err)
        _erca_fallback = APIRouter()

        @_erca_fallback.get("/api/rca/dashboard")
        async def rca_fallback_dashboard():
            return {"total_analyses": 0, "error": _erca_err_detail}

        app.include_router(_erca_fallback)
        availability["enterprise_rca"] = False
        log.warning(f"Enterprise Root Cause Analysis routes unavailable: {_erca_err_detail}")

    try:
        from backend.api.enterprise_pipeline_routes import router as enterprise_pipeline_router
        app.include_router(enterprise_pipeline_router)
        log.info("Enterprise Pipeline routes registered at /api/pipeline")
        availability["enterprise_pipeline"] = True
    except Exception as _epipe_err:
        _epipe_err_detail = str(_epipe_err)
        _epipe_fallback = APIRouter()

        @_epipe_fallback.get("/api/pipeline/pipelines")
        async def pipeline_fallback_list():
            return {"pipelines": [], "error": _epipe_err_detail}

        app.include_router(_epipe_fallback)
        availability["enterprise_pipeline"] = False
        log.warning(f"Enterprise Pipeline routes unavailable: {_epipe_err_detail}")

    try:
        from backend.api.enterprise_architecture_routes import router as enterprise_architecture_router
        app.include_router(enterprise_architecture_router)
        log.info("Enterprise Architecture routes registered at /api/architecture")
        availability["enterprise_architecture"] = True
    except Exception as _earch_err:
        _earch_err_detail = str(_earch_err)
        _earch_fallback = APIRouter()

        @_earch_fallback.get("/api/architecture/projects")
        async def architecture_fallback_list():
            return {"projects": [], "error": _earch_err_detail}

        app.include_router(_earch_fallback)
        availability["enterprise_architecture"] = False
        log.warning(f"Enterprise Architecture routes unavailable: {_earch_err_detail}")

    try:
        from backend.api.enterprise_engineering_executive_routes import router as engineering_executive_router
        app.include_router(engineering_executive_router)
        log.info("Engineering Executive routes registered at /api/engineering-executive")
        availability["engineering_executive"] = True
    except Exception as _ee_exec_err:
        _ee_exec_err_detail = str(_ee_exec_err)
        _ee_exec_fallback = APIRouter()

        @_ee_exec_fallback.get("/api/engineering-executive/tasks")
        async def ee_exec_tasks_fallback():
            return {"tasks": [], "error": _ee_exec_err_detail}

        @_ee_exec_fallback.get("/api/engineering-executive/plans")
        async def ee_exec_plans_fallback():
            return {"plans": [], "error": _ee_exec_err_detail}

        @_ee_exec_fallback.get("/api/engineering-executive/dashboard")
        async def ee_exec_dashboard_fallback():
            return {"total_tasks": 0, "total_plans": 0, "error": _ee_exec_err_detail}

        app.include_router(_ee_exec_fallback)
        availability["engineering_executive"] = False
        log.warning(f"Engineering Executive routes unavailable: {_ee_exec_err_detail}")

    try:
        from backend.api.research_routes import router as research_router
        app.include_router(research_router)
        log.info("Live Research routes registered")
        availability["research"] = True
    except Exception as _research_err:
        _research_err_detail = str(_research_err)
        _research_fallback = APIRouter()

        @_research_fallback.get("/api/research/health")
        async def research_fallback_health():
            return {"status": "unavailable", "detail": _research_err_detail}

        app.include_router(_research_fallback)
        availability["research"] = False
        log.warning(f"Research routes unavailable: {_research_err_detail}")

    try:
        from backend.api.computer_routes import router as computer_router
        app.include_router(computer_router)
        log.info("Computer Agent routes registered")
        availability["computer"] = True
    except Exception as _computer_err:
        _computer_err_detail = str(_computer_err)
        _computer_fallback = APIRouter()

        @_computer_fallback.get("/computer/health")
        async def computer_health_fallback():
            return {"status": "unavailable", "detail": _computer_err_detail}

        @_computer_fallback.get("/computer/status")
        async def computer_status_fallback():
            return {"status": "unavailable", "active_missions": 0, "detail": _computer_err_detail}

        @_computer_fallback.get("/computer/tasks")
        async def computer_tasks_fallback():
            return {"active_tasks": [], "completed_tasks": [], "total_completed": 0}

        app.include_router(_computer_fallback)
        availability["computer"] = False
        log.warning(f"Computer Agent routes unavailable: {_computer_err_detail}")

    try:
        from backend.api.operator_routes import router as operator_router
        app.include_router(operator_router)
        log.info("Operator routes registered")
        availability["operator"] = True
    except Exception as _op_err:
        _op_err_detail = str(_op_err)
        _op_fallback = APIRouter()

        @_op_fallback.get("/operator/health")
        async def operator_health_fallback():
            return {"status": "unavailable", "detail": _op_err_detail}

        @_op_fallback.get("/operator/active-missions")
        async def operator_active_fallback():
            return {"missions": [], "count": 0, "detail": _op_err_detail}

        app.include_router(_op_fallback)
        availability["operator"] = False
        log.warning(f"Operator routes unavailable: {_op_err_detail}")

    try:
        from backend.api.workspace_routes import router as workspace_router
        app.include_router(workspace_router)
        log.info("Workspace Intelligence routes registered")
        availability["workspace"] = True
    except Exception as _ws_err:
        _ws_err_detail = str(_ws_err)
        _ws_fallback = APIRouter()

        @_ws_fallback.get("/api/workspace/health")
        async def workspace_health_fallback():
            return {"status": "unavailable", "detail": _ws_err_detail}

        app.include_router(_ws_fallback)
        availability["workspace"] = False
        log.warning(f"Workspace routes unavailable: {_ws_err_detail}")

    try:
        from backend.voice_v2.voice_routes_v2 import router as voice_v2_router
        app.include_router(voice_v2_router)
        log.info("Voice V2 routes registered")
        availability["voice_v2"] = True
    except Exception as _voice_v2_err:
        _voice_v2_err_detail = str(_voice_v2_err)
        _voice_v2_fallback = APIRouter()

        @_voice_v2_fallback.get("/api/voice/v2/health")
        async def voice_v2_health_fallback():
            return {"status": "unavailable", "detail": _voice_v2_err_detail}

        app.include_router(_voice_v2_fallback)
        availability["voice_v2"] = False
        log.warning(f"Voice V2 routes unavailable: {_voice_v2_err_detail}")

    try:
        from backend.api.llm_health_routes import router as llm_health_router
        app.include_router(llm_health_router)
        log.info("LLM health routes registered at /health/llm")
        availability["llm_health"] = True
    except Exception as _llm_health_err:
        _llm_health_err_detail = str(_llm_health_err)
        _llm_health_fallback = APIRouter()

        @_llm_health_fallback.get("/health/llm")
        async def llm_health_fallback():
            return {"status": "unavailable", "detail": _llm_health_err_detail}

        app.include_router(_llm_health_fallback)
        availability["llm_health"] = False
        log.warning(f"LLM health routes unavailable: {_llm_health_err_detail}")

    try:
        from backend.api.system_health_routes import router as system_health_router
        app.include_router(system_health_router)
        log.info("System health route registered at /health/system")
        availability["system_health"] = True
    except Exception as _sys_health_err:
        _sys_health_err_detail = str(_sys_health_err)
        _sys_health_fallback = APIRouter()

        @_sys_health_fallback.get("/health/system")
        async def system_health_fallback():
            return {"status": "unavailable", "detail": _sys_health_err_detail}

        app.include_router(_sys_health_fallback)
        availability["system_health"] = False
        log.warning(f"System health route unavailable: {_sys_health_err_detail}")

    try:
        from backend.api.metrics_routes import PrometheusMiddleware
        from backend.api.metrics_routes import router as metrics_router
        app.add_middleware(PrometheusMiddleware)
        app.include_router(metrics_router)
        log.info("Prometheus /metrics endpoint registered")
        availability["metrics"] = True
    except Exception as _prom_err:
        availability["metrics"] = False
        log.warning(f"Prometheus metrics unavailable: {_prom_err}")

    try:
        from backend.api.cost_routes import router as cost_router
        app.include_router(cost_router)
        log.info("Cost Engine routes registered at /api/costs")
        availability["cost"] = True
    except Exception as _cost_err:
        _cost_err_detail = str(_cost_err)
        _cost_fallback = APIRouter()

        @_cost_fallback.get("/api/costs/summary")
        async def cost_summary_fallback():
            return {"error": _cost_err_detail, "today_spend": 0.0, "month_spend": 0.0}

        app.include_router(_cost_fallback)
        availability["cost"] = False
        log.warning(f"Cost Engine routes unavailable: {_cost_err_detail}")

    try:
        from backend.api.connector_routes import router as connector_router
        app.include_router(connector_router)
        log.info("Enterprise Connector routes registered at /api/connectors")
        availability["connector"] = True
    except Exception as _conn_err:
        _conn_err_detail = str(_conn_err)
        _conn_fallback = APIRouter()

        @_conn_fallback.get("/api/connectors")
        async def connector_list_fallback():
            return {"connectors": [], "total": 0, "detail": _conn_err_detail}

        app.include_router(_conn_fallback)
        availability["connector"] = False
        log.warning(f"Enterprise Connector routes unavailable: {_conn_err_detail}")

    try:
        from backend.api.connector_activity_routes import router as connector_activity_router
        app.include_router(connector_activity_router)
        log.info("Connector Activity routes registered at /api/connectors/activity")
        availability["connector_activity"] = True
    except Exception as _conn_act_err:
        _conn_act_err_detail = str(_conn_act_err)
        _conn_act_fallback = APIRouter()

        @_conn_act_fallback.get("/api/connectors/activity")
        async def connector_activity_fallback():
            return {"activities": [], "total": 0, "detail": _conn_act_err_detail}

        app.include_router(_conn_act_fallback)
        availability["connector_activity"] = False
        log.warning(f"Connector Activity routes unavailable: {_conn_act_err_detail}")

    try:
        from backend.api.executive_dashboard_routes import router as executive_dashboard_router
        app.include_router(executive_dashboard_router)
        log.info("Executive Dashboard routes registered at /api/executive/dashboard")
        availability["executive_dashboard"] = True
    except Exception as _exec_dash_err:
        _exec_dash_err_detail = str(_exec_dash_err)
        _exec_dash_fallback = APIRouter()

        @_exec_dash_fallback.get("/api/executive/dashboard")
        async def executive_dashboard_fallback():
            return {
                "reasoning": {"sessions": [], "activeSessionId": None, "isReasoning": False, "error": None},
                "simulation": {"simulations": [], "activeSimulationId": None, "isSimulating": False, "error": None},
                "adaptiveExecution": {"missionId": None, "activeRecoveries": [], "completedRecoveries": [], "failedRecoveries": [], "adaptiveMode": True, "healthScore": 100, "isHealing": False},
                "observation": {"categories": [], "metrics": [], "alerts": [], "isObserving": True, "lastUpdate": None},
                "decisionMemory": {"decisions": [], "isLoading": False, "error": None},
                "runtimeMetrics": {"activeExecutions": 0, "completedExecutions": 0, "failedExecutions": 0, "activeAgents": 0, "totalTokens": 0, "avgLatency": 0, "confidenceScore": 0, "healthScore": 100},
            }

        app.include_router(_exec_dash_fallback)
        availability["executive_dashboard"] = False
        log.warning(f"Executive Dashboard routes unavailable: {_exec_dash_err_detail}")

    try:
        from backend.api.audit_routes import router as audit_router
        app.include_router(audit_router, prefix="/api")
        log.info("Audit routes registered at /api/audit")
        availability["audit"] = True
    except Exception as exc:
        availability["audit"] = False
        log.warning("audit_routes not available: %s", exc)

    try:
        from backend.api.backup_routes import router as backup_router
        app.include_router(backup_router, prefix="/api")
        log.info("Backup routes registered at /api/backup")
        availability["backup"] = True
    except Exception as exc:
        availability["backup"] = False
        log.warning("backup_routes not available: %s", exc)

    try:
        from backend.api.department_routes import router as department_router
        app.include_router(department_router, prefix="/api")
        log.info("Department routes registered at /api/departments")
        availability["department"] = True
    except Exception as exc:
        availability["department"] = False
        log.warning("department_routes not available: %s", exc)

    try:
        from backend.api.diagnostics_routes import router as diagnostics_router
        app.include_router(diagnostics_router, prefix="/api")
        log.info("Diagnostics routes registered at /api/diagnostics")
        availability["diagnostics"] = True
    except Exception as exc:
        availability["diagnostics"] = False
        log.warning("diagnostics_routes not available: %s", exc)

    try:
        from backend.api.health_center_routes import router as health_center_router
        app.include_router(health_center_router, prefix="/api")
        log.info("Health Center routes registered at /api/health-center")
        availability["health_center"] = True
    except Exception as exc:
        availability["health_center"] = False
        log.warning("health_center_routes not available: %s", exc)

    try:
        from backend.api.maintenance_routes import router as maintenance_router
        app.include_router(maintenance_router, prefix="/api")
        log.info("Maintenance routes registered at /api/maintenance")
        availability["maintenance"] = True
    except Exception as exc:
        availability["maintenance"] = False
        log.warning("maintenance_routes not available: %s", exc)

    try:
        from backend.api.operational_reports_routes import router as operational_reports_router
        app.include_router(operational_reports_router, prefix="/api")
        log.info("Operational Reports routes registered at /api/operational-reports")
        availability["operational_reports"] = True
    except Exception as exc:
        availability["operational_reports"] = False
        log.warning("operational_reports_routes not available: %s", exc)

    try:
        from backend.api.organization_routes import router as organization_router
        app.include_router(organization_router, prefix="/api")
        log.info("Organization routes registered at /api/organization")
        availability["organization"] = True
    except Exception as exc:
        availability["organization"] = False
        log.warning("organization_routes not available: %s", exc)

    try:
        from backend.api.project_routes import router as project_router
        app.include_router(project_router, prefix="/api")
        log.info("Project routes registered at /api/projects")
        availability["project"] = True
    except Exception as exc:
        availability["project"] = False
        log.warning("project_routes not available: %s", exc)

    try:
        from backend.api.vcs_routes import router as vcs_router
        app.include_router(vcs_router)
        log.info("VCS routes registered at /api/vcs")
        availability["vcs"] = True
    except Exception as exc:
        availability["vcs"] = False
        log.warning("vcs_routes not available: %s", exc)

    try:
        from backend.api.organization_department_routes import router as organization_department_router
        app.include_router(organization_department_router)
        log.info("Organization Department routes registered at /api/organization/departments")
        availability["organization_department"] = True
    except Exception as exc:
        availability["organization_department"] = False
        log.warning("organization_department_routes not available: %s", exc)

    try:
        from backend.api.enterprise_cognition_routes import router as cognition_router
        app.include_router(cognition_router)
        log.info("Enterprise Continuous Cognition routes registered at /api/cognition")
        availability["cognition"] = True
    except Exception as _cog_err:
        _cog_err_detail = str(_cog_err)
        _cog_fallback = APIRouter()

        @_cog_fallback.get("/api/cognition/status")
        async def cognition_status_fallback():
            return {"state": "unavailable", "detail": _cog_err_detail}

        @_cog_fallback.get("/api/cognition/health")
        async def cognition_health_fallback():
            return {"status": "unavailable", "detail": _cog_err_detail}

        app.include_router(_cog_fallback)
        availability["cognition"] = False
        log.warning(f"Enterprise Continuous Cognition routes unavailable: {_cog_err_detail}")

    try:
        from backend.api.enterprise_execution_routes import router as execution_router
        app.include_router(execution_router)
        log.info("Enterprise Execution Engine routes registered at /api/engineering/execution")
        availability["execution"] = True
    except Exception as _exec_err:
        _exec_detail = str(_exec_err)
        _exec_fallback = APIRouter()

        @_exec_fallback.get("/api/engineering/execution/dashboard")
        async def execution_dashboard_fallback():
            return {"total_executions": 0, "active_count": 0, "by_status": {}, "recent_executions": [], "status": "unavailable", "detail": _exec_detail}

        app.include_router(_exec_fallback)
        availability["execution"] = False
        log.warning(f"Enterprise Execution Engine routes unavailable: {_exec_detail}")

    # Mission Intelligence Engine routes (Phase 12A)
    try:
        from backend.mission_intel.routes import router as mission_intel_router
        app.include_router(mission_intel_router)
        availability["mission_intel"] = True
        log.info("Mission Intelligence Engine routes registered at /api/mission-intel")
    except Exception as _mi_err:
        _mi_detail = str(_mi_err)
        _mi_fallback = APIRouter()

        @_mi_fallback.get("/api/mission-intel/health")
        async def mission_intel_health_fallback():
            return {"status": "unavailable", "detail": _mi_detail}

        @_mi_fallback.post("/api/mission-intel/analyze")
        async def mission_intel_analyze_fallback():
            return {"status": "unavailable", "detail": _mi_detail}

        @_mi_fallback.post("/api/mission-intel/decompose")
        async def mission_intel_decompose_fallback():
            return {"status": "unavailable", "detail": _mi_detail}

        @_mi_fallback.post("/api/mission-intel/full-pipeline")
        async def mission_intel_pipeline_fallback():
            return {"status": "unavailable", "detail": _mi_detail}

        @_mi_fallback.post("/api/mission-intel/plan")
        async def mission_intel_plan_fallback():
            return {"status": "unavailable", "detail": _mi_detail}

        app.include_router(_mi_fallback)
        availability["mission_intel"] = False
        log.warning(f"Mission Intelligence Engine routes unavailable: {_mi_detail}")

    # Cognitive Memory Runtime routes (Phase 13A)
    try:
        from backend.cognitive_memory.routes import router as cognitive_memory_router
        app.include_router(cognitive_memory_router)
        availability["cognitive_memory"] = True
        log.info("Cognitive Memory Runtime routes registered at /api/memory")
    except Exception as _cm_err:
        _cm_detail = str(_cm_err)
        _cm_fallback = APIRouter()

        @_cm_fallback.get("/api/memory/health")
        async def cognitive_memory_health_fallback():
            return {"status": "unavailable", "detail": _cm_detail}

        @_cm_fallback.post("/api/memory/context")
        async def cognitive_memory_context_fallback():
            return {"status": "unavailable", "detail": _cm_detail}

        @_cm_fallback.post("/api/memory/snapshot")
        async def cognitive_memory_snapshot_fallback():
            return {"status": "unavailable", "detail": _cm_detail}

        @_cm_fallback.post("/api/memory/restore")
        async def cognitive_memory_restore_fallback():
            return {"status": "unavailable", "detail": _cm_detail}

        app.include_router(_cm_fallback)
        availability["cognitive_memory"] = False
        log.warning(f"Cognitive Memory Runtime routes unavailable: {_cm_detail}")

    try:
        from backend.orchestrator.routes import router as orchestrator_router
        app.include_router(orchestrator_router)
        availability["orchestrator"] = True
        log.info("Autonomous Mission Orchestrator routes registered at /api/orchestrator")
    except Exception as _orch_err:
        _orch_detail = str(_orch_err)
        _orch_fallback = APIRouter()

        @_orch_fallback.get("/api/orchestrator/health")
        async def orchestrator_health_fallback():
            return {"status": "unavailable", "detail": _orch_detail}

        @_orch_fallback.post("/api/orchestrator/start")
        async def orchestrator_start_fallback():
            return {"status": "unavailable", "detail": _orch_detail}

        @_orch_fallback.get("/api/orchestrator/list")
        async def orchestrator_list_fallback():
            return {"missions": [], "total": 0, "detail": _orch_detail}

        app.include_router(_orch_fallback)
        availability["orchestrator"] = False
        log.warning(f"Autonomous Mission Orchestrator routes unavailable: {_orch_detail}")

    try:
        from backend.agents.routes import router as agents_router
        app.include_router(agents_router)
        availability["agents"] = True
        log.info("Multi-Agent Runtime routes registered at /api/agents")
    except Exception as _agents_err:
        _agents_detail = str(_agents_err)
        _agents_fallback = APIRouter()

        @_agents_fallback.get("/api/agents/health")
        async def agents_health_fallback():
            return {"status": "unavailable", "detail": _agents_detail}

        app.include_router(_agents_fallback)
        availability["agents"] = False
        log.warning(f"Multi-Agent Runtime routes unavailable: {_agents_detail}")

    try:
        from backend.mcp.routes import router as mcp_router
        app.include_router(mcp_router)
        availability["mcp"] = True
        log.info("MCP Gateway routes registered at /api/v2/mcp")
    except Exception as _mcp_err:
        _mcp_detail = str(_mcp_err)
        _mcp_fallback = APIRouter()

        @_mcp_fallback.get("/api/v2/mcp/health")
        async def mcp_health_fallback():
            return {"status": "unavailable", "detail": _mcp_detail}

        app.include_router(_mcp_fallback)
        availability["mcp"] = False
        log.warning(f"MCP Gateway routes unavailable: {_mcp_detail}")

    try:
        from backend.fleet.routes import router as fleet_router
        app.include_router(fleet_router)
        availability["fleet"] = True
        log.info("Fleet Management routes registered at /api/v2/fleets")
    except Exception as _fleet_err:
        _fleet_detail = str(_fleet_err)
        _fleet_fallback = APIRouter()

        @_fleet_fallback.get("/api/v2/fleets/health")
        async def fleet_health_fallback():
            return {"status": "unavailable", "detail": _fleet_detail}

        app.include_router(_fleet_fallback)
        availability["fleet"] = False
        log.warning(f"Fleet Management routes unavailable: {_fleet_detail}")

    try:
        from backend.workflow_designer.routes import router as wf_router
        app.include_router(wf_router)
        availability["workflow_designer"] = True
        log.info("Workflow Designer routes registered at /api/v2/workflows")
    except Exception as _wf_err:
        _wf_detail = str(_wf_err)
        _wf_fallback = APIRouter()

        @_wf_fallback.get("/api/v2/workflows/health")
        async def wf_health_fallback():
            return {"status": "unavailable", "detail": _wf_detail}

        app.include_router(_wf_fallback)
        availability["workflow_designer"] = False
        log.warning(f"Workflow Designer routes unavailable: {_wf_detail}")

    return availability
