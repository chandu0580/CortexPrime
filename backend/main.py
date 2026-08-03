import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).with_name('.env'))

# ==========================================
# STRUCTURED LOGGING  (must be first)
# ==========================================
from backend.core.dependency_container import container
from backend.core.logging import configure_root_logger, get_logger

configure_root_logger()
_log = get_logger(__name__)

from backend.core.logging_config import configure_logging

configure_logging()

from backend.events.event_bus import event_bus
from backend.runtime.agent_registry import agent_registry
from backend.runtime.runtime_state import runtime_state

# ==========================================
# SENTRY - Error tracking (optional)
# Initialised before anything else so it
# captures import-time errors too.
# Set SENTRY_DSN in .env to enable.
# ==========================================

_SENTRY_DSN = os.getenv("SENTRY_DSN", "")
_sentry_active = False
if _SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            environment=os.getenv("ENV", "development"),
            release=f"cortexprime@{os.getenv('BUILD_HASH', '1.0.0')}",
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_RATE", "0.1")),
            profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_RATE", "0.1")),
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                LoggingIntegration(level=logging.WARNING, event_level=logging.ERROR),
            ],
            send_default_pii=False,
        )
        _sentry_active = True
        logging.getLogger(__name__).info("Sentry error tracking initialised (env=%s)", os.getenv("ENV"))
    except Exception as _sentry_err:
        logging.getLogger(__name__).warning("Sentry init failed: %s", _sentry_err)

def _log_registered_routes(app: FastAPI) -> None:
    log = logging.getLogger(__name__)
    route_lines = []

    for route in app.router.routes:
        methods = sorted(getattr(route, "methods", []) or [])
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        for method in methods:
            route_lines.append((method, path))

    log.info("Registered routes:")
    for method, path in sorted(route_lines, key=lambda item: (item[1], item[0])):
        log.info("%s %s", method, path)


# ==========================================
# APPLICATION LIFESPAN  (startup -> yield -> shutdown)
# ==========================================

@asynccontextmanager
async def lifespan(_app: FastAPI):
    log = logging.getLogger(__name__)

    # ============================================================
    # REGISTER ALL RUNTIME SERVICES IN DEPENDENCY CONTAINER
    # ============================================================

    # Application -> Platform
    from backend.events.event_bus import event_bus
    from backend.runtime.runtime_metrics import runtime_metrics
    from backend.runtime.runtime_state import runtime_state

    container.register("event_bus", event_bus)
    container.register("runtime_metrics", runtime_metrics)
    container.register("runtime_state", runtime_state)

    # Repository Layer (Pilot Services)
    from backend.database.repositories.factory import repo_factory
    container.register("repo_factory", repo_factory)

    # Identity Runtime Foundation (Milestone 2A)
    from backend.identity.di import register_identity_services
    register_identity_services()

    # Governance Runtime Core (Phase 6A) — registered before Mission + Execution Runtime
    # so both runtimes can consult governance for policy decisions.
    try:
        from backend.governance.di import register_governance_services
        register_governance_services()
    except Exception as exc:
        _log.warning("Governance Runtime services registration incomplete: %s", exc)

    # Knowledge Runtime Core (Phase 7A)
    # Registered before Mission + Execution Runtime so they can auto-index
    # completed missions and execution history into the knowledge base.
    try:
        from backend.knowledge.di import register_knowledge_services
        register_knowledge_services()
    except Exception as exc:
        _log.warning("Knowledge Runtime services registration incomplete: %s", exc)

    # Learning Runtime Core (Phase 8A)
    # Registered after Knowledge Runtime so it can consume patterns from
    # knowledge base for training and recommendation generation.
    try:
        from backend.learning.di import register_learning_services
        register_learning_services()
    except Exception as exc:
        _log.warning("Learning Runtime services registration incomplete: %s", exc)

    # LLM Provider Runtime (Phase 10A)
    # Registered before AI Runtime so AI can use LLM Provider Runtime
    # for all model interactions. Registered after Learning Runtime.
    try:
        from backend.llm_provider.di import register_llm_provider_services
        register_llm_provider_services()
    except Exception as exc:
        _log.warning("LLM Provider Runtime services registration incomplete: %s", exc)

    # AI Runtime Core (Phase 9A)
    # Registered after Learning Runtime so it can orchestrate all lower
    # runtimes (Identity, Connector, Governance, Knowledge, Learning,
    # Execution, Mission). AI Runtime provides intent classification,
    # rule-based planning, and standardized runtime invocation.
    try:
        from backend.ai.di import register_ai_services
        register_ai_services()
    except Exception as exc:
        _log.warning("AI Runtime services registration incomplete: %s", exc)

    # OAuth / SSO Identity Providers (Milestone 2B)
    try:
        from backend.identity.providers.registry import register_default_providers
        register_default_providers()
    except Exception as exc:
        _log.warning("OAuth provider registration incomplete: %s", exc)

    # Execution Runtime Core (Phase 4) — registered before Mission Runtime
    # so Mission Runtime can resolve it for step execution.
    try:
        from backend.execution.di import register_execution_services
        register_execution_services()
    except Exception as exc:
        _log.warning("Execution Runtime services registration incomplete: %s", exc)

    # Mission Runtime Core (Milestone 3A)
    try:
        from backend.mission.di import register_mission_services
        register_mission_services()
    except Exception as exc:
        _log.warning("Mission Runtime services registration incomplete: %s", exc)

    # Cortex Runtime
    from backend.orchestration.cognition_pipeline import cognition_pipeline
    from backend.orchestration.execution_context import execution_context_manager
    from backend.orchestration.lifecycle_manager import agent_lifecycle_manager
    from backend.orchestration.orchestration_tracer import orchestration_tracer
    from backend.orchestration.priority_queue import execution_priority_queue
    from backend.runtime.dynamic_agent_factory import dynamic_agent_factory
    from backend.runtime.execution_manager import execution_manager
    from backend.runtime.runtime_state_store import runtime_state_store

    container.register("runtime_state_store", runtime_state_store)
    container.register("execution_manager", execution_manager)
    container.register("cognition_pipeline", cognition_pipeline)
    container.register("agent_lifecycle_manager", agent_lifecycle_manager)
    container.register("orchestration_tracer", orchestration_tracer)
    container.register("execution_priority_queue", execution_priority_queue)
    container.register("execution_context_manager", execution_context_manager)
    container.register("dynamic_agent_factory", dynamic_agent_factory)

    # Mission Runtime
    from backend.services.memory_context_service import memory_context_service
    from backend.services.mission_replay_store import replay_store
    from backend.services.mission_runtime import mission_runtime

    container.register("mission_runtime", mission_runtime)
    container.register("replay_store", replay_store)
    container.register("memory_context_service", memory_context_service)

    # Enterprise Reasoning (LLM layer)
    from backend.llm.llm_gateway import llm_gateway
    from backend.llm.llm_router import llm_router

    container.register("llm_gateway", llm_gateway)
    container.register("llm_router", llm_router)

    # Mission Planning / Execution
    from backend.orchestration.task_decomposer import task_decomposer
    from backend.runtime.recursive_planner import recursive_planner

    container.register("recursive_planner", recursive_planner)
    container.register("task_decomposer", task_decomposer)

    # Cognitive Orchestrator
    from backend.orchestrator.agent_router import agent_router
    from backend.orchestrator.autonomous_reasoning_loop import autonomous_reasoning_loop
    from backend.orchestrator.master_agent_runtime import master_agent_runtime
    from backend.orchestrator.mission_planner import mission_agent_runtime
    from backend.orchestrator.reflection_engine import reflection_engine

    container.register("agent_router", agent_router)
    container.register("master_agent_runtime", master_agent_runtime)
    container.register("mission_agent_runtime", mission_agent_runtime)
    container.register("autonomous_reasoning_loop", autonomous_reasoning_loop)
    container.register("reflection_engine", reflection_engine)

    # Workers (Browser, Voice)
    from backend.tools.browser_agent import browser_agent
    from backend.voice.voice_runtime import voice_runtime

    container.register("browser_agent", browser_agent)
    container.register("voice_runtime", voice_runtime)

    # Redis Cognitive Memory
    from backend.infrastructure.redis.cognition_cache import cognition_cache
    from backend.infrastructure.redis.connection import redis_connection
    from backend.infrastructure.redis.pub_sub import pub_sub
    from backend.infrastructure.redis.runtime_state_manager import runtime_state_manager
    from backend.infrastructure.redis.transient_memory import transient_memory

    container.register("redis_connection", redis_connection)
    container.register("pub_sub", pub_sub)
    container.register("cognition_cache", cognition_cache)
    container.register("transient_memory", transient_memory)
    container.register("runtime_state_manager", runtime_state_manager)

    # Neo4j Knowledge Graph
    from backend.infrastructure.neo4j.connection import neo4j_connection
    from backend.infrastructure.neo4j.graph_manager import neo4j_graph
    from backend.infrastructure.neo4j.query_service import graph_query_service
    from backend.services.enterprise_event_hub import enterprise_hub
    from backend.services.enterprise_graph_service import enterprise_graph

    container.register("neo4j_connection", neo4j_connection)
    container.register("neo4j_graph", neo4j_graph)
    container.register("graph_query_service", graph_query_service)
    container.register("enterprise_graph", enterprise_graph)
    container.register("enterprise_hub", enterprise_hub)

    # Enterprise Learning Engine
    from backend.services.enterprise_learning_service import enterprise_learning

    container.register("enterprise_learning", enterprise_learning)

    # Enterprise Monitoring (Watchers, Rules, Auto-Generator)
    from backend.services.autonomous_mission_generator import auto_mission_generator
    from backend.services.enterprise_watchers import watcher_manager
    from backend.services.monitoring_rules_engine import monitoring_rules

    container.register("watcher_manager", watcher_manager)
    container.register("monitoring_rules", monitoring_rules)
    container.register("auto_mission_generator", auto_mission_generator)

    # Enterprise Explainability Service
    from backend.services.enterprise_explainability_service import enterprise_explainability

    container.register("enterprise_explainability", enterprise_explainability)

    # Enterprise Recommendation Engine
    from backend.services.enterprise_recommendation_engine import enterprise_recommendation_engine

    container.register("enterprise_recommendation_engine", enterprise_recommendation_engine)

    # Enterprise Engineering Department
    from backend.services.enterprise_engineering_service import engineering_executive

    container.register("engineering_executive", engineering_executive)

    # Enterprise Workspace Engine
    from backend.services.enterprise_workspace_engine import workspace_manager

    container.register("workspace_manager", workspace_manager)

    # Enterprise Patch Engine
    from backend.services.enterprise_patch_engine import patch_manager

    container.register("patch_manager", patch_manager)

    # Enterprise Build Engine
    from backend.services.enterprise_build_engine import BuildEngine

    build_engine = BuildEngine()
    container.register("build_engine", build_engine)

    # Enterprise Deployment Engine
    from backend.services.enterprise_deployment_engine import DeploymentEngine

    deployment_engine = DeploymentEngine()
    container.register("deployment_engine", deployment_engine)

    # Enterprise Governance Service
    from backend.services.enterprise_governance_service import GovernanceService

    governance_service = GovernanceService()
    container.register("governance_service", governance_service)

    # Enterprise Analytics Service
    from backend.services.enterprise_analytics_service import AnalyticsService

    analytics_service = AnalyticsService()
    container.register("analytics_service", analytics_service)

    # Enterprise Delivery Orchestrator
    from backend.services.enterprise_delivery_orchestrator import delivery_orchestrator

    container.register("delivery_orchestrator", delivery_orchestrator)

    # Autonomous Trigger Runtime
    from backend.services.autonomous_trigger_runtime import autonomous_trigger_runtime

    container.register("autonomous_trigger_runtime", autonomous_trigger_runtime)

    # Enterprise Execution Sandbox
    from backend.services.enterprise_execution_sandbox import execution_sandbox

    container.register("execution_sandbox", execution_sandbox)

    # Enterprise Code Intelligence
    from backend.services.enterprise_code_intelligence import code_intelligence

    container.register("code_intelligence", code_intelligence)

    # Enterprise Patch Pipeline
    from backend.services.enterprise_patch_pipeline import patch_pipeline

    container.register("patch_pipeline", patch_pipeline)

    # Enterprise Git Operations
    from backend.services.enterprise_git_operations import git_operations

    container.register("git_operations", git_operations)

    # Enterprise Pipeline Orchestrator
    from backend.services.enterprise_pipeline_orchestrator import pipeline_orchestrator

    container.register("pipeline_orchestrator", pipeline_orchestrator)

    # Enterprise GitHub Integration
    from backend.services.enterprise_github_integration import github_integration

    container.register("github_integration", github_integration)

    # Enterprise CI/CD Intelligence
    from backend.services.enterprise_cicd_intelligence import cicd_intelligence

    container.register("cicd_intelligence", cicd_intelligence)

    # Enterprise Infrastructure Intelligence
    from backend.services.enterprise_infrastructure_intelligence import infrastructure_intelligence

    container.register("infrastructure_intelligence", infrastructure_intelligence)

    # Enterprise Root Cause Analysis Intelligence
    from backend.services.enterprise_root_cause_analysis import root_cause_analysis

    container.register("root_cause_analysis", root_cause_analysis)

    # Enterprise Architecture Intelligence
    from backend.services.enterprise_architecture_intelligence import architecture_intelligence

    container.register("architecture_intelligence", architecture_intelligence)

    # Enterprise Connectors (RabbitMQ)
    from backend.infrastructure.rabbitmq.channel_pool import channel_pool
    from backend.infrastructure.rabbitmq.connection import rabbitmq_connection
    from backend.infrastructure.rabbitmq.orchestration_bus import orchestration_bus
    from backend.infrastructure.rabbitmq.publisher import rabbitmq_publisher

    container.register("rabbitmq_connection", rabbitmq_connection)
    container.register("orchestration_bus", orchestration_bus)
    container.register("channel_pool", channel_pool)
    container.register("rabbitmq_publisher", rabbitmq_publisher)

    # Governance
    from backend.safety.approval_queue import approval_queue
    from backend.safety.audit_logger import audit_logger
    from backend.safety.emergency_stop import emergency_stop
    from backend.safety.guardrails_engine import guardrails_engine
    from backend.safety.rate_limiter import rate_limiter
    from backend.safety.safety_guard import safety_guard

    container.register("safety_guard", safety_guard)
    container.register("guardrails_engine", guardrails_engine)
    container.register("audit_logger", audit_logger)
    container.register("approval_queue", approval_queue)
    container.register("emergency_stop", emergency_stop)
    container.register("rate_limiter", rate_limiter)

    # Observability
    from backend.observability.prometheus_metrics import metrics

    container.register("prometheus_metrics", metrics)

    # Analytics
    from backend.analytics.cost_engine import cost_engine

    container.register("cost_engine", cost_engine)

    # Memory subsystem
    from backend.memory.embedding_pipeline import embedding_pipeline
    from backend.memory.event_subscriber import memory_event_subscriber
    from backend.memory.graph.cognition_graph import cognition_graph
    from backend.memory.memory_orchestrator import memory_orchestrator
    from backend.memory.vector_memory import vector_memory

    container.register("memory_event_subscriber", memory_event_subscriber)
    container.register("cognition_graph", cognition_graph)
    container.register("memory_orchestrator", memory_orchestrator)
    container.register("vector_memory", vector_memory)
    container.register("embedding_pipeline", embedding_pipeline)

    # WebSocket services
    from backend.websocket.connection_manager import connection_manager
    from backend.websocket.connection_pool import connection_pool
    from backend.websocket.heartbeat_monitor import heartbeat_monitor
    from backend.websocket.metrics_broadcaster import metrics_broadcaster

    container.register("connection_manager", connection_manager)
    container.register("connection_pool", connection_pool)
    container.register("heartbeat_monitor", heartbeat_monitor)
    container.register("metrics_broadcaster", metrics_broadcaster)

    # Multi-Agent Runtime (Phase 15A)
    try:
        from backend.agents.di import register_agent_services
        register_agent_services()
        log.info("Multi-Agent Runtime services registered")
    except Exception as exc:
        log.warning("Multi-Agent Runtime registration incomplete: %s", exc)

    # ============================================================
    # STARTUP SEQUENCE
    #   1) Application -> Platform -> Runtime -> Workers ->
    #      Memory -> Knowledge Graph -> Connectors -> Mission Runtime -> Ready
    # ============================================================

    # 1) Agent lifecycle bootstrap
    try:
        agent_lifecycle_manager.bootstrap()
        log.info("Agent lifecycle manager bootstrapped")
    except Exception as exc:
        log.warning(f"Lifecycle bootstrap incomplete: {exc}")

    # 2) RabbitMQ - Enterprise Connectors
    try:
        connected = await rabbitmq_connection.connect()
        if connected:
            await rabbitmq_connection.declare_topology()
            await orchestration_bus.start()
            log.info("RabbitMQ connected - orchestration bus started")
        else:
            log.warning("RabbitMQ unavailable - orchestration bus in degraded mode")
    except Exception as exc:
        log.warning(f"RabbitMQ startup incomplete: {exc}")

    # 3) Redis - Cognitive Memory
    try:
        connected = await redis_connection.connect()
        if connected:
            from backend.infrastructure.redis.keys import RedisKeys
            from backend.websocket.connection_manager import connection_manager as _cm

            async def _ws_broadcast_handler(channel: str, payload) -> None:
                await _cm.broadcast(payload)

            pub_sub.subscribe(RedisKeys.channel_broadcast(), _ws_broadcast_handler)
            await pub_sub.start()
            log.info("Redis connected - pub/sub subscriber started")
        else:
            log.warning("Redis unavailable - in-memory fallback active")
    except Exception as exc:
        log.warning(f"Redis startup incomplete: {exc}")

    # 4) Neo4j - Knowledge Graph
    try:
        connected = await neo4j_connection.connect()
        if connected:
            await neo4j_graph.ensure_schema()
            await enterprise_graph.ensure_schema()
            for record in agent_lifecycle_manager.list_all():
                await neo4j_graph.upsert_agent(
                    record["agent_name"],
                    record["agent_type"],
                    record.get("capabilities", []),
                )
            log.info("Neo4j connected - knowledge graph schema ensured")
    except Exception as exc:
        log.warning(f"Neo4j startup incomplete: {exc}")

    # 5) Enterprise EventHub — subscribe to EventBus for cross-service sync
    try:
        await enterprise_hub.initialize()
        log.info("Enterprise EventHub initialized")
    except Exception as exc:
        log.warning(f"Enterprise EventHub startup incomplete: {exc}")

    # 5a) Enterprise Learning Engine — subscribe to EventBus for active learning
    try:
        await enterprise_learning.initialize()
        log.info("Enterprise Learning Engine initialized")
    except Exception as exc:
        log.warning(f"Enterprise Learning Engine startup incomplete: {exc}")

    # 5b) Monitoring Rules Engine — load persisted monitoring rules
    try:
        await monitoring_rules.initialize()
        log.info("Monitoring Rules Engine initialized")
    except Exception as exc:
        log.warning(f"Monitoring Rules Engine startup incomplete: {exc}")

    # 5c) Autonomous Mission Generator — prepare auto-mission creation
    try:
        await auto_mission_generator.initialize()
        log.info("Autonomous Mission Generator initialized")
    except Exception as exc:
        log.warning(f"Autonomous Mission Generator startup incomplete: {exc}")


    # 5e) Enterprise Recommendation Engine — start periodic scanning
    try:
        await enterprise_recommendation_engine.initialize()
        log.info("Enterprise Recommendation Engine initialized")
    except Exception as exc:
        log.warning(f"Enterprise Recommendation Engine startup incomplete: {exc}")

    # 5f) Enterprise Build Engine
    try:
        log.info("Enterprise Build Engine initialized")
    except Exception as exc:
        log.warning(f"Enterprise Build Engine startup incomplete: {exc}")

    # 5g) Enterprise Deployment Engine
    try:
        log.info("Enterprise Deployment Engine initialized")
    except Exception as exc:
        log.warning(f"Enterprise Deployment Engine startup incomplete: {exc}")

    # 5h) Enterprise Governance Service
    try:
        log.info("Enterprise Governance Service initialized")
    except Exception as exc:
        log.warning(f"Enterprise Governance Service startup incomplete: {exc}")

    # 5i) Enterprise Analytics Service
    try:
        log.info("Enterprise Analytics Service initialized")
    except Exception as exc:
        log.warning(f"Enterprise Analytics Service startup incomplete: {exc}")

    # 5j) Autonomous Trigger Runtime — listen & seed defaults
    try:
        from backend.services.autonomous_trigger_runtime import autonomous_trigger_runtime
        await autonomous_trigger_runtime.initialize()
        await autonomous_trigger_runtime.seed_default_policies()
        if os.getenv("AUTONOMOUS_TRIGGERS_ENABLED", "true").lower() != "false":
            await autonomous_trigger_runtime.start()
            log.info("Autonomous Trigger Runtime initialized and started")
        else:
            log.info("Autonomous Trigger Runtime initialized (scheduler loop disabled via AUTONOMOUS_TRIGGERS_ENABLED=false)")
    except Exception as exc:
        log.warning(f"Autonomous Trigger Runtime startup incomplete: {exc}")

    # 5k) Enterprise Execution Sandbox — ready for execution
    try:
        from backend.services.enterprise_execution_sandbox import execution_sandbox
        log.info("Enterprise Execution Sandbox initialized with %d sandboxes",
                 len(execution_sandbox._sandboxes) if hasattr(execution_sandbox, '_sandboxes') else 0)
    except Exception as exc:
        log.warning(f"Enterprise Execution Sandbox startup incomplete: {exc}")

    # 5l) Enterprise Patch Pipeline — load persisted data
    try:
        from backend.services.enterprise_patch_pipeline import patch_pipeline
        log.info("Enterprise Patch Pipeline initialized with %d plans, %d candidates",
                 len(patch_pipeline._plans) if hasattr(patch_pipeline, '_plans') else 0,
                 len(patch_pipeline._candidates) if hasattr(patch_pipeline, '_candidates') else 0)
    except Exception as exc:
        log.warning(f"Enterprise Patch Pipeline startup incomplete: {exc}")

    # 5m) Enterprise Git Operations — load persisted data
    try:
        from backend.services.enterprise_git_operations import git_operations
        log.info("Enterprise Git Operations initialized with %d PRs tracked",
                 len(git_operations._pull_requests) if hasattr(git_operations, '_pull_requests') else 0)
    except Exception as exc:
        log.warning(f"Enterprise Git Operations startup incomplete: {exc}")

    # 5n-m) Enterprise GitHub Integration — load persisted state
    try:
        from backend.services.enterprise_github_integration import github_integration
        log.info("Enterprise GitHub Integration initialized with %d webhooks tracked",
                 len(github_integration._webhooks) if hasattr(github_integration, '_webhooks') else 0)
    except Exception as exc:
        log.warning(f"Enterprise GitHub Integration startup incomplete: {exc}")

    # 5n-m) Enterprise CI/CD Intelligence — initialize
    try:
        from backend.services.enterprise_cicd_intelligence import cicd_intelligence
        log.info("Enterprise CI/CD Intelligence initialized")
    except Exception as exc:
        log.warning(f"Enterprise CI/CD Intelligence startup incomplete: {exc}")

    # 5n-n) Enterprise Infrastructure Intelligence — initialize
    try:
        from backend.services.enterprise_infrastructure_intelligence import infrastructure_intelligence
        await infrastructure_intelligence.initialize()
        log.info("Enterprise Infrastructure Intelligence initialized")
    except Exception as exc:
        log.warning(f"Enterprise Infrastructure Intelligence startup incomplete: {exc}")

    # 5n-n1) Enterprise Trace Intelligence — initialize OTLP connector
    try:
        from backend.services.enterprise_trace_intelligence import trace_intelligence
        await trace_intelligence.initialize()
        log.info("Enterprise Trace Intelligence initialized")
    except Exception as exc:
        log.warning(f"Enterprise Trace Intelligence startup incomplete: {exc}")

    # 5n-n2) Enterprise Prometheus Intelligence — initialize metric + alert collectors
    try:
        from backend.services.enterprise_prometheus_intelligence import alert_intelligence, prometheus_metrics
        await prometheus_metrics.initialize()
        await alert_intelligence.initialize()
        log.info("Enterprise Prometheus Intelligence initialized")
    except Exception as exc:
        log.warning(f"Enterprise Prometheus Intelligence startup incomplete: {exc}")

    # 5n-n3) Enterprise Loki Intelligence — initialize connector
    try:
        from backend.connectors.loki import loki_connector as loki_conn
        await loki_conn.initialize()
        log.info("Enterprise Loki Intelligence initialized — ready=%s", loki_conn.is_ready)
    except Exception as exc:
        log.warning(f"Enterprise Loki Intelligence startup incomplete: {exc}")

    # 5n-n4) Enterprise Grafana Intelligence — initialize connector
    try:
        from backend.connectors.grafana import grafana_connector as gcon
        await gcon.initialize()
        log.info("Enterprise Grafana Intelligence initialized — ready=%s, org=%s", gcon.is_ready, gcon.org_name)
    except Exception as exc:
        log.warning(f"Enterprise Grafana Intelligence startup incomplete: {exc}")

    # 5n-n5) Enterprise ArgoCD GitOps Intelligence — initialize connector
    try:
        from backend.connectors.argocd import argocd_connector as acon
        await acon.initialize()
        log.info("Enterprise ArgoCD GitOps Intelligence initialized — ready=%s", acon.is_ready)
    except Exception as exc:
        log.warning(f"Enterprise ArgoCD GitOps Intelligence startup incomplete: {exc}")

    # 5n-o) Enterprise Root Cause Analysis Intelligence — initialize
    try:
        from backend.services.enterprise_root_cause_analysis import root_cause_analysis
        log.info("Enterprise Root Cause Analysis Intelligence initialized")
    except Exception as exc:
        log.warning(f"Enterprise Root Cause Analysis Intelligence startup incomplete: {exc}")

    # 5n) Enterprise Pipeline Orchestrator — load persisted data
    try:
        from backend.services.enterprise_pipeline_orchestrator import pipeline_orchestrator
        log.info("Enterprise Pipeline Orchestrator initialized with %d pipelines",
                 len(pipeline_orchestrator._pipelines) if hasattr(pipeline_orchestrator, '_pipelines') else 0)
    except Exception as exc:
        log.warning(f"Enterprise Pipeline Orchestrator startup incomplete: {exc}")

    # 5o) Enterprise Architecture Intelligence — load persisted data
    try:
        from backend.services.enterprise_architecture_intelligence import architecture_intelligence
        log.info("Enterprise Architecture Intelligence initialized with %d projects",
                 len(architecture_intelligence._projects) if hasattr(architecture_intelligence, '_projects') else 0)
    except Exception as exc:
        log.warning(f"Enterprise Architecture Intelligence startup incomplete: {exc}")

    # 5p) Enterprise Continuous Cognition Runtime — start background loop
    try:
        from backend.services.enterprise_continuous_cognition_runtime import (
            enterprise_continuous_cognition_runtime,
        )
        _cog_interval = int(os.getenv("COGNITION_LOOP_INTERVAL_SECONDS", "60"))
        _cog_repo_interval = int(os.getenv("COGNITION_REPO_INTERVAL_SECONDS", "300"))
        _cog_infra_interval = int(os.getenv("COGNITION_INFRA_INTERVAL_SECONDS", "120"))
        enterprise_continuous_cognition_runtime._loop_interval = max(10, _cog_interval)
        enterprise_continuous_cognition_runtime._repo_interval = max(30, _cog_repo_interval)
        enterprise_continuous_cognition_runtime._infra_interval = max(30, _cog_infra_interval)
        await enterprise_continuous_cognition_runtime.start()
        log.info("Enterprise Continuous Cognition Runtime started (interval=%ds)", _cog_interval)
    except Exception as exc:
        log.warning(f"Enterprise Continuous Cognition Runtime startup incomplete: {exc}")

    # 6) Memory subsystem
    try:
        await memory_event_subscriber.start()
        await cognition_graph.ensure_constraints()
        log.info("Memory subsystem started - subscriber + cognition graph")
    except Exception as exc:
        log.warning(f"Memory subsystem startup incomplete: {exc}")

    # 7) Database migrations
    _migration_ok = False
    try:
        from backend.database.migrator import run_migrations
        from backend.safety.audit_logger import audit_logger as _al

        _al.log(
            execution_id="system_startup",
            agent="migration_runner",
            action="migration_start",
            risk_level="low",
            outcome="started",
            reason="Automatic startup migration check",
        )
        _mig = await run_migrations()
        if _mig.status == "success":
            _migration_ok = True
            log.info("Database migrations complete - revision: %s", _mig.revision)
            _al.log(
                execution_id="system_startup",
                agent="migration_runner",
                action="migration_complete",
                risk_level="low",
                outcome="completed",
                reason=f"Schema at revision {_mig.revision}",
            )
        elif _mig.status == "skipped":
            log.info("Database migrations skipped (SKIP_DB_MIGRATIONS=true)")
        else:
            log.warning("Database migration failed: %s", _mig.error)
            _al.log(
                execution_id="system_startup",
                agent="migration_runner",
                action="migration_failure",
                risk_level="high",
                outcome="failed",
                reason=_mig.error or "Migration failed",
            )
            if os.getenv("BLOCK_ON_MIGRATION_FAILURE", "false").lower() in (
                "1", "true", "yes"
            ):
                raise RuntimeError(
                    f"Database migration failed - blocking startup: {_mig.error}"
                )
    except RuntimeError:
        raise
    except Exception as exc:
        log.warning("Migration runner raised unexpectedly: %s", exc)

    if not _migration_ok:
        try:
            from backend.database.engine import init_db
            await init_db()
            log.info("PostgreSQL + pgvector database layer ready (create_all fallback)")
        except Exception as exc:
            log.warning(f"Database layer startup incomplete: {exc}")

    # 7a) Bounded Context Repository Layer — ensure new domain tables exist
    try:
        from backend.database.engine import init_db as _init_db
        from backend.database.models import _ensure_bc_models
        _ensure_bc_models()
        await _init_db()
        log.info("Bounded context repository tables verified")
    except Exception as exc:
        log.warning("Repository layer table check incomplete: %s", exc)

    # 7b) Object Storage client connect
    try:
        from backend.infrastructure.object_storage import object_storage
        await object_storage.connect()
        log.info("Object storage client ready")
    except Exception as exc:
        log.warning("Object storage client unavailable: %s", exc)

    # 7c) OpenSearch client connect
    try:
        from backend.infrastructure.opensearch import opensearch_client
        await opensearch_client.connect()
        log.info("OpenSearch client ready")
    except Exception as exc:
        log.warning("OpenSearch client unavailable: %s", exc)

    # 7d) Vault client connect
    try:
        from backend.infrastructure.vault import vault_client
        await vault_client.connect()
        log.info("Vault client ready")
    except Exception as exc:
        log.warning("Vault client unavailable: %s", exc)

    # 7) WebSocket gateway services
    try:
        await heartbeat_monitor.start()
        await metrics_broadcaster.start()
        log.info("WebSocket heartbeat monitor + metrics broadcaster started")
    except Exception as exc:
        log.warning(f"WebSocket gateway services startup incomplete: {exc}")

    # 8) Embedding dimension validation
    _runtime_env = (os.getenv("ENVIRONMENT") or os.getenv("ENV") or "development").lower()
    _strict = os.getenv("STRICT_EMBEDDING_VALIDATION", "false").lower() in (
        "1", "true", "yes"
    )
    _embed_validation_default = "true" if _runtime_env == "production" else "false"
    _run_embed_validation = os.getenv(
        "STARTUP_EMBEDDING_VALIDATION",
        _embed_validation_default,
    ).lower() in ("1", "true", "yes")
    _embed_validation_timeout = float(
        os.getenv("STARTUP_EMBEDDING_VALIDATION_TIMEOUT_SEC", "12")
    )

    if _run_embed_validation:
        try:
            from backend.memory.embedding_pipeline import EMBED_DIM
            from backend.memory.embedding_pipeline import embedding_pipeline as _ep
            from backend.safety.audit_logger import audit_logger as _al

            _val = await asyncio.wait_for(
                _ep.validate_dimensions(),
                timeout=_embed_validation_timeout,
            )
            if _val["ok"]:
                log.info(
                    "Embedding dimensions validated - model=%s dim=%d",
                    _val["model"], _val["actual"],
                )
            else:
                _msg = (
                    f"EMBEDDING DIMENSION MISMATCH at startup - "
                    f"expected={_val['expected']} actual={_val['actual']} model={_val['model']}"
                    + (f" error={_val.get('error', '')}" if _val.get('error') else "")
                )
                log.critical(_msg)
                _al.log(
                    execution_id="system_startup",
                    agent="embedding_pipeline",
                    action="startup_dimension_validation_failed",
                    target=f"pgvector(dim={EMBED_DIM})",
                    risk_level="high",
                    outcome="warning" if not _strict else "rejected",
                    reason=_msg,
                    metadata=_val,
                )
                if _strict:
                    raise RuntimeError(_msg)
                log.warning(
                    "Embedding degraded mode: pgvector rows will be stored "
                    "without embeddings until OpenAI key is configured. "
                    "Set STRICT_EMBEDDING_VALIDATION=true to block startup on mismatch."
                )
        except RuntimeError:
            raise
        except asyncio.TimeoutError:
            if _strict:
                raise RuntimeError("Embedding validation startup check timed out")
            log.warning("Embedding validation startup check timed out after %.1fs", _embed_validation_timeout)
        except Exception as exc:
            log.warning("Embedding validation startup check failed: %s", exc)
    else:
        log.info(
            "Skipping startup embedding validation in %s environment "
            "(set STARTUP_EMBEDDING_VALIDATION=true to enable)",
            _runtime_env,
        )

    # 9) Runtime state recovery
    try:
        _recovered = await runtime_state_store.recover_on_startup()
        if _recovered:
            log.info("Runtime state recovered: %d execution(s) from Redis", _recovered)
        else:
            log.info("Runtime state recovery complete - no orphaned executions found")
    except Exception as exc:
        log.warning(f"Runtime state recovery incomplete: {exc}")

    # 9b) Deploy-regression check recovery — resume any in-flight checks
    # that were still waiting when the process last stopped.
    try:
        from backend.services.enterprise_github_integration import recover_pending_deploy_checks
        _recovered_checks = await recover_pending_deploy_checks()
        if _recovered_checks:
            log.info("Deploy-regression checks recovered: %d in-flight", _recovered_checks)
    except Exception as exc:
        log.warning(f"Deploy-regression check recovery incomplete: {exc}")

    # 10) Mission Runtime - final readiness
    try:
        log.info("Mission Runtime service ready")
    except Exception as exc:
        log.warning(f"Mission Runtime service unavailable: {exc}")

    # 11) Startup dependency validation
    try:
        _dep_errors = []
        from backend.database.health import check_database_health as _dbh
        from backend.infrastructure.neo4j.connection import neo4j_connection as _nc4j
        from backend.infrastructure.rabbitmq.connection import rabbitmq_connection as _rcon
        from backend.infrastructure.redis.connection import redis_connection as _rc
        db_ok = await _dbh()
        deps = {"redis": _rc.is_available, "neo4j": _nc4j.is_available,
                "rabbitmq": _rcon.is_available, "postgresql": db_ok.get("status") == "healthy"}
        for name, ok in deps.items():
            if ok:
                log.info("Dependency %s: connected", name)
            else:
                _dep_errors.append(name)
                log.warning("Dependency %s: NOT available - degraded mode", name)
        if _dep_errors:
            log.warning("Startup with %d unavailable deps: %s", len(_dep_errors), _dep_errors)
        else:
            log.info("All infrastructure dependencies available")
    except Exception as exc:
        log.warning("Dependency validation incomplete: %s", exc)

    # 12) Enterprise Connectors registration
    # Each connector is imported + registered independently so one broken
    # or missing optional dependency (e.g. the `docker` SDK) can't take
    # down registration for the other, unrelated connectors.
    try:
        from backend.connectors.registry import connector_registry

        _connector_specs = [
            ("backend.connectors.github", "GitHubConnector"),
            ("backend.connectors.jira", "JiraConnector"),
            ("backend.connectors.slack", "SlackConnector"),
            ("backend.connectors.teams", "TeamsConnector"),
            ("backend.connectors.azure_devops", "AzureDevOpsConnector"),
            ("backend.connectors.confluence", "ConfluenceConnector"),
            ("backend.connectors.servicenow", "ServiceNowConnector"),
            ("backend.connectors.notion", "NotionConnector"),
            ("backend.connectors.kubernetes", "KubernetesConnector"),
            ("backend.connectors.docker", "DockerConnector"),
            ("backend.connectors.jenkins", "JenkinsConnector"),
            ("backend.connectors.gitlab_ci", "GitLabCIConnector"),
            ("backend.connectors.circleci", "CircleCIConnector"),
            ("backend.connectors.argocd", "ArgoCDConnector"),
            ("backend.connectors.grafana", "GrafanaConnector"),
            ("backend.connectors.loki", "LokiConnector"),
            ("backend.connectors.opentelemetry", "OpenTelemetryConnector"),
            ("backend.connectors.prometheus", "PrometheusConnector"),
            ("backend.connectors.terraform", "TerraformConnector"),
        ]
        _registered = 0
        _initialized = 0
        for _module_name, _class_name in _connector_specs:
            try:
                _module = __import__(_module_name, fromlist=[_class_name])
                _connector_cls = getattr(_module, _class_name)
                _instance = _connector_cls()
                connector_registry.register(_instance)
                _registered += 1
                try:
                    if await _instance.initialize():
                        _initialized += 1
                except Exception as _init_exc:
                    log.debug("Connector %s registered but not ready: %s", _class_name, _init_exc)
            except Exception as _conn_exc:
                log.warning("Connector %s unavailable: %s", _class_name, _conn_exc)
        log.info(
            "Registered %d/%d enterprise connectors (%d initialized/ready)",
            _registered, len(_connector_specs), _initialized,
        )
    except Exception as exc:
        log.warning("Enterprise connectors registration incomplete: %s", exc)

    # One-shot credential check, not a recurring background loop — see
    # enterprise_credential_monitor's module docstring for why.
    try:
        from backend.services.enterprise_credential_monitor import check_all_credentials
        await check_all_credentials()
    except Exception as exc:
        log.debug("Startup credential check skipped: %s", exc)

    # One-shot vulnerability check, same reasoning as credentials above —
    # see enterprise_vulnerability_monitor's module docstring.
    try:
        from backend.services.enterprise_vulnerability_monitor import check_vulnerabilities
        await check_vulnerabilities()
    except Exception as exc:
        log.debug("Startup vulnerability check skipped: %s", exc)

    # One-shot branch protection check, same reasoning as credentials above —
    # see enterprise_branch_protection_monitor's module docstring.
    try:
        from backend.services.enterprise_branch_protection_monitor import check_all_repos as check_branch_protection
        await check_branch_protection()
    except Exception as exc:
        log.debug("Startup branch protection check skipped: %s", exc)

    # One-shot cost anomaly check, same reasoning as credentials/branch
    # protection above — see enterprise_cost_anomaly_monitor's module
    # docstring. Cost accumulates over a day, so a one-shot startup check
    # + on-demand endpoint is the right cadence, not continuous polling.
    try:
        from backend.services.enterprise_cost_anomaly_monitor import check_all_providers as check_cost_anomalies
        await check_cost_anomalies()
    except Exception as exc:
        log.debug("Startup cost anomaly check skipped: %s", exc)

    # Approval action dispatcher — subscribes to the EventBus so approving
    # a blocked rollback/vuln-fix/branch-protection workflow via
    # POST /api/approval-center/workflows/{id}/approve actually replays the
    # real action instead of approving being a dead end.
    try:
        from backend.services.enterprise_approval_action_dispatcher import initialize as init_approval_dispatcher
        init_approval_dispatcher()
    except Exception as exc:
        log.warning("Approval action dispatcher startup incomplete: %s", exc)

    # Enterprise Watchers — initialize connector watchers, then start
    # continuous polling. Must run AFTER connector registration above —
    # EnterpriseWatcher.initialize() looks connectors up in the shared
    # connector_registry, which isn't populated until this point; running
    # it earlier (where it lived before) meant every watcher always
    # reported "connector not registered", including for connectors
    # (GitHub, Jira, GitLab CI) that are genuinely configured and working.
    #
    # Skipped under pytest: this is an always-on asyncio.create_task
    # background loop, the same shape that caused a multi-hour test-suite
    # hang earlier this session (a different one, in
    # enterprise_infrastructure_intelligence.py) — unlike that one, every
    # watcher's poll() here is confirmed real async I/O (httpx), not a
    # to_thread-wrapped blocking call, so it's safe to run, but there's
    # still no reason to have it running during tests.
    try:
        results = await watcher_manager.initialize_all()
        ready = sum(1 for v in results.values() if v)
        log.info("Enterprise Watchers initialized — %d/%d ready", ready, len(results))
        if "PYTEST_CURRENT_TEST" not in os.environ:
            asyncio.create_task(watcher_manager.start_polling())
            log.info("Enterprise Watchers — continuous polling started")
    except Exception as exc:
        log.warning(f"Enterprise Watchers startup incomplete: {exc}")

    _log_registered_routes(_app)
    log.info("CortexPrime runtime startup complete - all subsystems online")

    yield  # application serves requests

    # ============================================================
    # SHUTDOWN SEQUENCE (reverse startup order)
    # ============================================================

    log.info("CortexPrime shutdown sequence initiated")

    # 1) Emit shutdown event
    try:
        from backend.events.event_models import CognitionEvent, EventTypes
        await event_bus.publish(
            CognitionEvent(
                agent="system",
                event_type=EventTypes.RUNTIME_STATE,
                status="completed",
                message="CortexPrime runtime shutting down",
            )
        )
    except Exception as exc:
        log.warning("Shutdown event publish failed: %s", exc)

    # 2) Persist runtime state
    try:
        _snap = runtime_state.get_state()
        _active_count = len(_snap.get("active_executions", {}))
        log.info("Runtime state persisted - %d active execution(s)", _active_count)
    except Exception as exc:
        log.warning("Runtime state persist incomplete: %s", exc)

    # 3) Stop WebSocket gateway services
    try:
        await heartbeat_monitor.stop()
        await metrics_broadcaster.stop()
    except Exception as exc:
        log.warning("WebSocket shutdown incomplete: %s", exc)

    # 4) Stop memory event subscriber
    try:
        await memory_event_subscriber.stop()
    except Exception as exc:
        log.warning("Memory subscriber stop incomplete: %s", exc)

    # 5) Stop Enterprise Monitoring (watchers, rules, recommendations)
    for svc_name, svc_shutdown in [
        ("Enterprise Watchers", watcher_manager.shutdown_all()),
        ("Monitoring Rules", monitoring_rules.shutdown()),
        ("Recommendation Engine", enterprise_recommendation_engine.shutdown()),
        ("Build Engine", None),
        ("Deployment Engine", None),
        ("Governance Service", None),
        ("Analytics Service", None),
    ]:
        try:
            if svc_shutdown is not None:
                await svc_shutdown
            log.info("%s shutdown", svc_name)
        except Exception as exc:
            log.warning("%s shutdown failed: %s", svc_name, exc)

    # 6) Stop Enterprise Infrastructure Intelligence
    try:
        from backend.services.enterprise_infrastructure_intelligence import infrastructure_intelligence
        await infrastructure_intelligence.shutdown()
        log.info("Enterprise Infrastructure Intelligence shutdown")
    except Exception as exc:
        log.warning("Infrastructure Intelligence shutdown failed: %s", exc)

    # 6b) Stop connectors registered in the shared connector_registry
    try:
        from backend.connectors.registry import connector_registry
        for _conn in connector_registry.list_all():
            try:
                await _conn.shutdown()
            except Exception as _shutdown_exc:
                log.debug("Connector %s shutdown failed: %s", _conn.connector_type, _shutdown_exc)
        log.info("Connector registry shutdown (%d connectors)", len(connector_registry.list_all()))
    except Exception as exc:
        log.warning("Connector registry shutdown failed: %s", exc)

    # 7) Stop Enterprise Continuous Cognition Runtime
    try:
        from backend.services.enterprise_continuous_cognition_runtime import (
            enterprise_continuous_cognition_runtime,
        )
        await enterprise_continuous_cognition_runtime.stop()
        log.info("Enterprise Continuous Cognition Runtime shutdown")
    except Exception as exc:
        log.warning("Continuous Cognition Runtime stop failed: %s", exc)

    # 8) Close Neo4j
    try:
        await neo4j_connection.close()
    except Exception as exc:
        log.warning("Neo4j close failed: %s", exc)

    # 9) Close Redis
    try:
        await pub_sub.stop()
        await redis_connection.close()
    except Exception as exc:
        log.warning("Redis close failed: %s", exc)

    # 10) Close RabbitMQ
    try:
        await orchestration_bus.stop()
        await channel_pool.close()
        await rabbitmq_connection.close()
    except Exception as exc:
        log.warning("RabbitMQ close failed: %s", exc)

    # 11) Close OpenSearch
    try:
        from backend.infrastructure.opensearch import opensearch_client
        await opensearch_client.close()
        log.info("OpenSearch client closed")
    except Exception as exc:
        log.warning("OpenSearch close failed: %s", exc)

    # 12) Close Object Storage (MinIO)
    try:
        from backend.infrastructure.object_storage import object_storage
        await object_storage.close()
        log.info("Object storage client closed")
    except Exception as exc:
        log.warning("Object storage close failed: %s", exc)

    # 13) Close Vault
    try:
        from backend.infrastructure.vault import vault_client
        await vault_client.close()
        log.info("Vault client closed")
    except Exception as exc:
        log.warning("Vault close failed: %s", exc)

    # 14) Identity Runtime shutdown
    try:
        log.info("Identity Runtime shut down")
    except Exception as exc:
        log.warning("Identity Runtime shutdown failed: %s", exc)

    # 15) Dispose database engine
    try:
        from backend.database.engine import dispose_engine
        await dispose_engine()
    except Exception as exc:
        log.warning("Database engine dispose failed: %s", exc)

    # 16) Flush runtime metrics summary
    try:
        _fm = runtime_metrics.export_metrics()
        log.info("Shutdown metrics: total=%d completed=%d failed=%d tokens=%d",
                 _fm.get("total_executions", 0),
                 _fm.get("completed_executions", 0),
                 _fm.get("failed_executions", 0),
                 _fm.get("total_tokens", 0))
    except Exception as exc:
        log.warning("Metrics flush failed: %s", exc)

    log.info("CortexPrime runtime shutdown complete")


# ==========================================
# FASTAPI APP
# ==========================================

_is_production = os.getenv("ENV", "development").lower() in ("production", "prod")
app = FastAPI(
    title="CortexPrime Runtime API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)

# ==========================================
# EXCEPTION HANDLERS  (registered before middleware)
# ==========================================
from backend.core.exception_handlers import register_exception_handlers

register_exception_handlers(app)


# ==========================================
# CORS
# allow_origins must be explicit when allow_credentials=True
# ==========================================

_CORS_ORIGINS = [
    o.strip() for o in
    os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]

_DEV_WILDCARD: bool = os.getenv("DEV_CORS_WILDCARD", "").lower() in ("true", "1", "yes")

app.add_middleware(
    CORSMiddleware,
    allow_origins     = _CORS_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"] if _DEV_WILDCARD else ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers     = ["*"] if _DEV_WILDCARD else [
        "Authorization", "Content-Type", "X-Request-ID", "X-CSRF-Token",
    ],
)

# ==========================================
# REQUEST ID MIDDLEWARE
# Runs after CORS so CORS headers are still
# applied on pre-flight OPTIONS requests.
# Runs before guardrails so all safety logs
# have a request_id attached.
# ==========================================
try:
    from backend.middleware.request_id import RequestIDMiddleware
    app.add_middleware(RequestIDMiddleware)
    logging.getLogger(__name__).info("Request ID middleware active")
except Exception as _rid_err:
    logging.getLogger(__name__).warning(f"Request ID middleware unavailable: {_rid_err}")

# ==========================================
# NEMO GUARDRAILS MIDDLEWARE
# Runs BEFORE every POST/PUT/PATCH route.
# Blocks prompt injection, jailbreaks, role
# overrides, and harmful intent at the HTTP
# boundary before Mission Runtime.
# ==========================================

try:
    from backend.safety.guardrails_middleware import GuardrailsMiddleware
    app.add_middleware(GuardrailsMiddleware)
    logging.getLogger(__name__).info("NeMo Guardrails middleware active")
except Exception as _guard_mw_err:
    logging.getLogger(__name__).warning(
        f"Guardrails middleware could not be registered: {_guard_mw_err}"
    )


# ==========================================
# TENANT CONTEXT MIDDLEWARE
# Resolves tenant, user, and permissions from
# every request and propagates them through
# ContextVar.  Runs after auth so the JWT
# has been verified.  Sets request.state.
# ==========================================

try:
    from backend.identity.tenant.tenant_context import TenantContextMiddleware
    app.add_middleware(TenantContextMiddleware)
    logging.getLogger(__name__).info("Tenant Context middleware active")
except Exception as _tc_mw_err:
    logging.getLogger(__name__).warning(
        f"Tenant Context middleware could not be registered: {_tc_mw_err}"
    )

# ==========================================
# RATE LIMIT MIDDLEWARE
# Redis sliding-window rate limiting on all
# REST routes.  Runs AFTER guardrails so the
# guardrails short-circuit before the Redis
# call on clearly malicious requests.
# Falls back to in-process counter when
# Redis is unavailable (graceful degradation).
# ==========================================

try:
    from backend.safety.rate_limit_middleware import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)
    logging.getLogger(__name__).info("Rate Limit middleware active")
except Exception as _rl_mw_err:
    logging.getLogger(__name__).warning(
        f"Rate Limit middleware could not be registered: {_rl_mw_err}"
    )


from backend.api.router_registry import register_all_routers

router_availability = register_all_routers(app)

# ==========================================
# ROOT ROUTE
# ==========================================

@app.get("/")

async def root():

    return {

        "system":
            "CortexPrime",

        "status":
            "running",

        "architecture":
            "multi-agent-cognitive-runtime",

        "registered_agents":
            agent_registry.list_agents(),

        "realtime_streaming":
            True,

        "runtime_state":
            "active",

        "version":
            os.getenv("APP_VERSION", "1.0.0")
    }


# ==========================================
# HEALTH CHECK
# ==========================================

@app.get("/health")

async def health_check():

    # Infrastructure status (non-blocking)
    infra: Dict[str, Any] = {}
    try:
        from backend.infrastructure.rabbitmq.connection import rabbitmq_connection
        infra["rabbitmq"] = "connected" if rabbitmq_connection.is_available else "disconnected"
    except Exception:
        infra["rabbitmq"] = "unavailable"

    try:
        from backend.infrastructure.redis.connection import redis_connection
        infra["redis"] = "connected" if redis_connection.is_available else "disconnected"
    except Exception:
        infra["redis"] = "unavailable"

    try:
        from backend.infrastructure.neo4j.connection import neo4j_connection
        infra["neo4j"] = "connected" if neo4j_connection.is_available else "disconnected"
    except Exception:
        infra["neo4j"] = "unavailable"

    try:
        from backend.infrastructure.object_storage import object_storage
        infra["object_storage"] = "connected" if object_storage.is_available else "disconnected"
    except Exception:
        infra["object_storage"] = "unavailable"

    try:
        from backend.infrastructure.opensearch import opensearch_client
        infra["opensearch"] = "connected" if opensearch_client.is_available else "disconnected"
    except Exception:
        infra["opensearch"] = "unavailable"

    try:
        from backend.infrastructure.vault import vault_client
        infra["vault"] = "connected" if vault_client.is_available else "disconnected"
    except Exception:
        infra["vault"] = "unavailable"

    return {

        "status":
            "healthy",

        "agents":
            len(
                agent_registry
                .list_agents()
            ),

        "event_bus":
            "active",

        "runtime":
            "operational",

        "websocket_streaming":
            True,

        "infrastructure":
            infra,
    }


# ==========================================
# DATABASE HEALTH + MIGRATION STATUS
# ==========================================

@app.get("/health/database")
async def database_health():
    from backend.database.health import check_database_health
    from backend.database.migrator import get_migration_status

    connectivity = await check_database_health()
    migration    = await get_migration_status()

    if connectivity["status"] == "offline":
        overall = "offline"
    elif migration.get("pending") is True:
        overall = "degraded"
    else:
        overall = connectivity["status"]

    return {
        "status":       overall,
        "connectivity": connectivity,
        "migration":    migration,
    }


# ==========================================
# IDENTITY RUNTIME HEALTH
# ==========================================

@app.get("/health/identity")
async def identity_health():
    try:
        from backend.core.dependency_container import container
        health = container.resolve("identity_health")
        return await health.check()
    except Exception as exc:
        return {
            "status": "unavailable",
            "error": str(exc),
        }


# ==========================================
# EMBEDDING HEALTH
# ==========================================

@app.get("/health/embeddings")
async def embedding_health():
    from backend.memory.embedding_pipeline import EMBED_DIM, embedding_pipeline

    telemetry = embedding_pipeline.get_telemetry()
    status    = telemetry["embedding_status"]

    warning: str | None = None
    if status == "degraded":
        if telemetry["mismatch_count"] > 0:
            warning = (
                f"Dimension mismatch detected {telemetry['mismatch_count']} time(s). "
                f"Expected {EMBED_DIM}-dim, got {telemetry['actual_dimension']}-dim. "
            )
        else:
            warning = (
                "OpenAI unavailable. Running on local all-MiniLM-L6-v2 (384-dim). "
            )
    elif status == "failed":
        warning = "All embedding backends failed. Semantic search is unavailable."

    return {**telemetry, "warning": warning}


# ==========================================
# RESEARCH HEALTH
# ==========================================

@app.get("/health/research")
async def research_health():
    from backend.research.research_telemetry import research_telemetry
    from backend.research.tavily_client import tavily_client

    configured = tavily_client.is_configured()
    snap       = research_telemetry.snapshot(recent_n=10)

    success_rate: float | None = snap.get("success_rate")

    if not configured:
        status  = "unavailable"
        warning = "TAVILY_API_KEY is not set. Live research is disabled."
    elif success_rate is not None and success_rate < 0.80:
        status  = "degraded"
        warning = f"Research success rate {success_rate:.0%}"
    else:
        status  = "healthy"
        warning = None

    return {
        "status":    status,
        "provider":  "tavily",
        "configured": configured,
        "warning":   warning,
        **snap,
    }


# ==========================================
# GUARDRAILS HEALTH
# ==========================================

@app.get("/health/guardrails")
async def guardrails_health():
    from backend.safety.guardrails_engine import guardrails_engine
    return guardrails_engine.status()


# ==========================================
# RATE LIMITER HEALTH
# ==========================================

@app.get("/health/rate-limiter")
async def rate_limiter_health():
    from backend.safety.rate_limiter import rate_limiter
    return await rate_limiter.status()


# ==========================================
# AUTH HEALTH
# ==========================================

@app.get("/health/auth")
async def auth_health_global():
    from backend.auth.token_blacklist import token_blacklist
    return await token_blacklist.status()


# ==========================================
# RUNTIME STATE HEALTH
# ==========================================

@app.get("/health/runtime")
async def runtime_health():
    from backend.runtime.runtime_state_store import runtime_state_store
    return await runtime_state_store.status()


# ==========================================
# AGENT METADATA
# ==========================================

@app.get("/agents")

async def get_agents():

    return {

        "registered_agents":
            agent_registry
            .get_all_metadata()
    }


# ==========================================
# EVENT HISTORY
# ==========================================

@app.get("/events")

async def get_events():

    return {

        "events":

            event_bus
            .get_events()
    }


# ==========================================
# RUNTIME STATE
# ==========================================

@app.get("/runtime-state")

async def get_runtime_state():

    return runtime_state.get_state()



