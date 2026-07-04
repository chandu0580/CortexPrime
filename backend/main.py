import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict
import logging
import os
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name('.env'))

# ==========================================
# STRUCTURED LOGGING  (must be first)
# ==========================================
from backend.core.logging import configure_root_logger, get_logger
from backend.core.dependency_container import container
configure_root_logger()
_log = get_logger(__name__)

from backend.websocket.websocket_router import router as websocket_router
from backend.runtime.agent_registry import agent_registry
from backend.events.event_bus import event_bus
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
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            environment=os.getenv("ENV", "development"),
            release=f"cortexprime@{os.getenv('BUILD_HASH', '3.0.0')}",
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

# ==========================================
# AUTH ROUTES  (JWT)
# ==========================================

try:
    from backend.api.auth_routes import router as auth_router
    _auth_available = True
except Exception as _auth_err:
    auth_router = None
    _auth_available = False
    logging.getLogger(__name__).warning(f"Auth routes unavailable: {_auth_err}")

# ==========================================
# MISSION EXECUTION ROUTES  (streaming)
# ==========================================

try:
    from backend.api.mission_execution_routes import router as mission_execution_router
    _mission_execution_available = True
except Exception as _me_err:
    mission_execution_router = None
    _mission_execution_available = False
    logging.getLogger(__name__).warning(f"Mission execution routes unavailable: {_me_err}")

# ==========================================
# NEW RUNTIME API
# ==========================================

try:
    from backend.api.runtime_api import router as runtime_api_router
    _runtime_api_available = True
except Exception as _runtime_api_err:
    runtime_api_router = None
    _runtime_api_available = False
    logging.getLogger(__name__).warning(
        f"Runtime API unavailable: {_runtime_api_err}"
    )

try:

    from backend.api.routes.mission_routes import (
        router as mission_router
    )

    from backend.api.routes.orchestrator_routes import (
        router as orchestrator_router
    )

    _advanced_api_routes_available = True

except Exception as route_import_error:

    mission_router = None

    orchestrator_router = None

    _advanced_api_routes_available = False


try:

    from backend.api.memory_routes import (
        router as memory_router
    )

    _memory_routes_available = True

except Exception as memory_route_error:

    memory_router = None

    _memory_routes_available = False

try:
    from backend.api.memory_explorer_routes import router as _memory_explorer_router
    _memory_explorer_available = True
except Exception as _mexpl_err:
    _memory_explorer_router = None
    _memory_explorer_available = False
    logging.getLogger(__name__).warning(f"Memory Explorer routes unavailable: {_mexpl_err}")


try:

    from backend.api.vector_search_routes import (
        router as vector_search_router
    )

    _vector_search_available = True

except Exception as _vector_search_err:

    vector_search_router = None

    _vector_search_available = False

    logging.getLogger(__name__).warning(
        f"Vector search routes unavailable: {_vector_search_err}"
    )

try:
    from backend.api.rabbitmq_routes import router as _rabbitmq_router
    _rabbitmq_routes_available = True
except Exception as _rmq_err:
    _rabbitmq_router = None
    _rabbitmq_routes_available = False
    logging.getLogger(__name__).warning(f"RabbitMQ routes unavailable: {_rmq_err}")

try:
    from backend.api.graph_routes import graph_router as _graph_router
    _graph_routes_available = True
except Exception as _graph_err:
    _graph_router = None
    _graph_routes_available = False
    logging.getLogger(__name__).warning(f"Graph routes unavailable: {_graph_err}")

try:
    from backend.api.mission_replay_routes import router as _replay_router
    _replay_routes_available = True
except Exception as _replay_err:
    _replay_router = None
    _replay_routes_available = False
    logging.getLogger(__name__).warning(f"Mission replay routes unavailable: {_replay_err}")

try:
    from backend.api.enterprise_replay_routes import router as _enterprise_replay_router
    _enterprise_replay_routes_available = True
except Exception as _enterprise_replay_err:
    _enterprise_replay_router = None
    _enterprise_replay_routes_available = False
    logging.getLogger(__name__).warning(f"Enterprise replay routes unavailable: {_enterprise_replay_err}")


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

    # Cortex Runtime
    from backend.runtime.runtime_state_store import runtime_state_store
    from backend.runtime.execution_manager import execution_manager
    from backend.orchestration.cognition_pipeline import cognition_pipeline
    from backend.orchestration.lifecycle_manager import agent_lifecycle_manager
    from backend.orchestration.orchestration_tracer import orchestration_tracer
    from backend.orchestration.priority_queue import execution_priority_queue
    from backend.orchestration.execution_context import execution_context_manager
    from backend.runtime.dynamic_agent_factory import dynamic_agent_factory

    container.register("runtime_state_store", runtime_state_store)
    container.register("execution_manager", execution_manager)
    container.register("cognition_pipeline", cognition_pipeline)
    container.register("agent_lifecycle_manager", agent_lifecycle_manager)
    container.register("orchestration_tracer", orchestration_tracer)
    container.register("execution_priority_queue", execution_priority_queue)
    container.register("execution_context_manager", execution_context_manager)
    container.register("dynamic_agent_factory", dynamic_agent_factory)

    # Mission Runtime
    from backend.services.mission_runtime import mission_runtime
    from backend.services.mission_replay_store import replay_store
    from backend.services.memory_context_service import memory_context_service

    container.register("mission_runtime", mission_runtime)
    container.register("replay_store", replay_store)
    container.register("memory_context_service", memory_context_service)

    # Enterprise Reasoning (LLM layer)
    from backend.llm.llm_gateway import llm_gateway
    from backend.llm.llm_router import llm_router

    container.register("llm_gateway", llm_gateway)
    container.register("llm_router", llm_router)

    # Mission Planning / Execution
    from backend.runtime.recursive_planner import recursive_planner
    from backend.orchestration.task_decomposer import task_decomposer

    container.register("recursive_planner", recursive_planner)
    container.register("task_decomposer", task_decomposer)

    # Cognitive Orchestrator
    from backend.orchestrator.agent_router import agent_router
    from backend.orchestrator.master_agent_runtime import master_agent_runtime
    from backend.orchestrator.mission_planner import mission_agent_runtime
    from backend.orchestrator.autonomous_reasoning_loop import autonomous_reasoning_loop
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
    from backend.infrastructure.redis.connection import redis_connection
    from backend.infrastructure.redis.pub_sub import pub_sub
    from backend.infrastructure.redis.cognition_cache import cognition_cache
    from backend.infrastructure.redis.transient_memory import transient_memory
    from backend.infrastructure.redis.runtime_state_manager import runtime_state_manager

    container.register("redis_connection", redis_connection)
    container.register("pub_sub", pub_sub)
    container.register("cognition_cache", cognition_cache)
    container.register("transient_memory", transient_memory)
    container.register("runtime_state_manager", runtime_state_manager)

    # Neo4j Knowledge Graph
    from backend.infrastructure.neo4j.connection import neo4j_connection
    from backend.infrastructure.neo4j.graph_manager import neo4j_graph
    from backend.infrastructure.neo4j.query_service import graph_query_service

    container.register("neo4j_connection", neo4j_connection)
    container.register("neo4j_graph", neo4j_graph)
    container.register("graph_query_service", graph_query_service)

    # Enterprise Connectors (RabbitMQ)
    from backend.infrastructure.rabbitmq.connection import rabbitmq_connection
    from backend.infrastructure.rabbitmq.orchestration_bus import orchestration_bus
    from backend.infrastructure.rabbitmq.channel_pool import channel_pool
    from backend.infrastructure.rabbitmq.publisher import rabbitmq_publisher

    container.register("rabbitmq_connection", rabbitmq_connection)
    container.register("orchestration_bus", orchestration_bus)
    container.register("channel_pool", channel_pool)
    container.register("rabbitmq_publisher", rabbitmq_publisher)

    # Governance
    from backend.safety.safety_guard import safety_guard
    from backend.safety.guardrails_engine import guardrails_engine
    from backend.safety.audit_logger import audit_logger
    from backend.safety.approval_queue import approval_queue
    from backend.safety.emergency_stop import emergency_stop
    from backend.safety.rate_limiter import rate_limiter

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
    from backend.memory.event_subscriber import memory_event_subscriber
    from backend.memory.graph.cognition_graph import cognition_graph
    from backend.memory.memory_orchestrator import memory_orchestrator
    from backend.memory.vector_memory import vector_memory
    from backend.memory.embedding_pipeline import embedding_pipeline

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
            from backend.websocket.connection_manager import connection_manager as _cm
            from backend.infrastructure.redis.keys import RedisKeys

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
            for record in agent_lifecycle_manager.list_all():
                await neo4j_graph.upsert_agent(
                    record["agent_name"],
                    record["agent_type"],
                    record.get("capabilities", []),
                )
            log.info("Neo4j connected - knowledge graph schema ensured")
    except Exception as exc:
        log.warning(f"Neo4j startup incomplete: {exc}")

    # 5) Memory subsystem
    try:
        await memory_event_subscriber.start()
        await cognition_graph.ensure_constraints()
        log.info("Memory subsystem started - subscriber + cognition graph")
    except Exception as exc:
        log.warning(f"Memory subsystem startup incomplete: {exc}")

    # 6) Database migrations
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
            import backend.database.models
            await init_db()
            log.info("PostgreSQL + pgvector database layer ready (create_all fallback)")
        except Exception as exc:
            log.warning(f"Database layer startup incomplete: {exc}")

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
            from backend.memory.embedding_pipeline import embedding_pipeline as _ep, EMBED_DIM
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

    # 10) Mission Runtime - final readiness
    try:
        from backend.services.mission_runtime import mission_runtime as _mr
        log.info("Mission Runtime service ready")
    except Exception as exc:
        log.warning(f"Mission Runtime service unavailable: {exc}")

    # 11) Startup dependency validation
    try:
        _dep_errors = []
        from backend.infrastructure.redis.connection import redis_connection as _rc
        from backend.infrastructure.neo4j.connection import neo4j_connection as _nc4j
        from backend.infrastructure.rabbitmq.connection import rabbitmq_connection as _rcon
        from backend.database.health import check_database_health as _dbh
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

    _log_registered_routes(_app)
    log.info("CortexPrime runtime startup complete - all subsystems online")

    yield  # application serves requests

    # ============================================================
    # SHUTDOWN SEQUENCE (reverse startup order)
    # ============================================================

    log.info("CortexPrime shutdown sequence initiated")

    # 1) Flush Prometheus metrics
    try:
        from backend.observability.prometheus_metrics import metrics as _pm
        log.info("Prometheus metrics flushed")
    except Exception:
        pass

    # 2) Persist runtime state
    try:
        _snap = runtime_state.get_state()
        _active_count = len(_snap.get("active_executions", {}))
        log.info("Runtime state persisted - %d active execution(s)", _active_count)
    except Exception as exc:
        log.warning("Runtime state persist incomplete: %s", exc)

    # 3) Emit shutdown event
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
    except Exception:
        pass

    # 4) Stop WebSocket gateway services
    try:
        await heartbeat_monitor.stop()
        await metrics_broadcaster.stop()
    except Exception:
        pass

    # 5) Stop memory event subscriber
    try:
        await memory_event_subscriber.stop()
    except Exception:
        pass

    # 6) Close Neo4j (Knowledge Graph)
    try:
        await neo4j_connection.close()
    except Exception:
        pass

    # 7) Close Redis (Cognitive Memory)
    try:
        await pub_sub.stop()
        await redis_connection.close()
    except Exception:
        pass

    # 8) Close RabbitMQ (Enterprise Connectors)
    try:
        await orchestration_bus.stop()
        await channel_pool.close()
        await rabbitmq_connection.close()
    except Exception:
        pass

    # 9) Dispose database engine
    try:
        from backend.database.engine import dispose_engine
        await dispose_engine()
    except Exception:
        pass

    # 10) Flush runtime metrics summary
    try:
        _fm = runtime_metrics.export_metrics()
        log.info("Shutdown metrics: total=%d completed=%d failed=%d tokens=%d",
                 _fm.get("total_executions", 0),
                 _fm.get("completed_executions", 0),
                 _fm.get("failed_executions", 0),
                 _fm.get("total_tokens", 0))
    except Exception:
        pass

    log.info("CortexPrime runtime shutdown complete")


# ==========================================
# FASTAPI APP
# ==========================================

_is_production = os.getenv("ENV", "development").lower() in ("production", "prod")
app = FastAPI(
    title="CortexPrime Runtime API",
    version="1.0.0-rc.1",
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

app.add_middleware(
    CORSMiddleware,
    allow_origins     = _CORS_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
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


# ==========================================
# INCLUDE ROUTERS
# ==========================================

app.include_router(
    websocket_router
)

# Auth FIRST before any protected routes
if _auth_available:
    app.include_router(auth_router)

# Mission execution router FIRST takes priority for /orchestrate
if _mission_execution_available:
    app.include_router(
        mission_execution_router,
        tags=["Mission Execution"]
    )

# ==========================================
# TELEMETRY ROUTER
# ==========================================

try:
    from backend.api.telemetry_routes import router as telemetry_router
    app.include_router(telemetry_router)
except Exception as _tel_err:
    logging.getLogger(__name__).warning(f"Telemetry routes unavailable: {_tel_err}")

# ==========================================
# RUNTIME API ROUTER
# ==========================================

if _runtime_api_available:
    app.include_router(runtime_api_router)

if _advanced_api_routes_available:

    app.include_router(
        mission_router,
        prefix="/api/missions",
        tags=["Missions"]
    )

    app.include_router(
        orchestrator_router,
        prefix="/api/orchestrator",
        tags=["Orchestrator"]
    )

else:

    fallback_router = APIRouter()

    @fallback_router.get("/api/missions/active")
    async def get_active_missions_fallback():
        return {
            "missions": [],
            "status": "degraded",
            "detail": "Advanced mission runtime unavailable",
        }

    @fallback_router.get("/api/missions/completed")
    async def get_completed_missions_fallback():
        return {
            "missions": [],
            "status": "degraded",
            "detail": "Advanced mission runtime unavailable",
        }

    @fallback_router.get("/api/orchestrator/loops/active")
    async def get_active_loops_fallback():
        return {
            "loops": [],
            "status": "degraded",
            "detail": "Orchestrator loop runtime unavailable",
        }

    @fallback_router.post("/api/orchestrator/autonomous")
    async def autonomous_execution_fallback(
        payload: Dict[str, Any]
    ):
        return {
            "status": "degraded",
            "accepted": False,
            "detail": "Autonomous execution unavailable",
            "payload_received": payload
        }

    app.include_router(fallback_router)


# ==========================================
# MEMORY ROUTES
# ==========================================

if _memory_routes_available:

    app.include_router(memory_router)

else:

    _mem_fallback = APIRouter()

    @_mem_fallback.get("/api/memory/status")
    async def memory_status_fallback():
        return {
            "status": "unavailable",
            "detail": "Memory layer failed to load",
        }

    app.include_router(_mem_fallback)


# ==========================================
# MEMORY EXPLORER ROUTES
# ==========================================

if _memory_explorer_available:
    app.include_router(_memory_explorer_router, prefix="/api")
    logging.getLogger(__name__).info("Memory Explorer routes registered at /api/memory/explorer")
else:
    _mexpl_fallback = APIRouter()

    @_mexpl_fallback.get("/api/memory/explorer/health")
    async def memory_explorer_health_fallback():
        return {"status": "unavailable", "detail": "Memory Explorer routes failed to initialise"}

    app.include_router(_mexpl_fallback)


# ==========================================
# GOVERNANCE CENTER ROUTES
# ==========================================

try:
    from backend.api.governance_center_routes import router as _gov_center_router
    _gov_center_available = True
except Exception as _gc_err:
    _gov_center_router = None
    _gov_center_available = False

if _gov_center_available:
    app.include_router(_gov_center_router, prefix="/api")
    logging.getLogger(__name__).info("Governance Center routes registered at /api/governance-center")
else:
    _gc_fallback = APIRouter()

    @_gc_fallback.get("/api/governance-center/health")
    async def governance_center_health_fallback():
        return {"status": "unavailable", "detail": "Governance Center routes failed to initialise"}

    app.include_router(_gc_fallback)


# ==========================================
# EXECUTIVE COMMAND CENTER ROUTES
# ==========================================

try:
    from backend.api.executive_routes import router as _executive_router
    _executive_available = True
except Exception as _exec_err:
    _executive_router = None
    _executive_available = False

if _executive_available:
    app.include_router(_executive_router, prefix="/api")
    logging.getLogger(__name__).info("Executive routes registered at /api/executive")
else:
    _exec_fallback = APIRouter()

    @_exec_fallback.get("/api/executive/health")
    async def executive_health_fallback():
        return {"status": "unavailable", "detail": "Executive routes failed to initialise"}

    app.include_router(_exec_fallback)


# ==========================================
# VECTOR SEARCH ROUTES
# ==========================================

if _vector_search_available:
    app.include_router(vector_search_router)

else:

    _vec_fallback = APIRouter()

    @_vec_fallback.get("/api/vector/health")
    async def vector_health_fallback():
        return {
            "status":  "unavailable",
            "pgvector": False,
            "detail":  "Vector search layer failed to initialise",
        }

    app.include_router(_vec_fallback)


# ==========================================
# RABBITMQ OBSERVABILITY ROUTES
# ==========================================

if _rabbitmq_routes_available:
    app.include_router(_rabbitmq_router)
else:
    _rmq_fallback = APIRouter()

    @_rmq_fallback.get("/api/rabbitmq/health")
    async def rabbitmq_health_fallback():
        return {"status": "unavailable", "detail": "RabbitMQ routes failed to initialise"}

    app.include_router(_rmq_fallback)


# ==========================================
# COGNITIVE GRAPH ROUTES
# ==========================================

if _graph_routes_available:
    app.include_router(_graph_router)
else:
    _graph_fallback = APIRouter()

    @_graph_fallback.get("/api/graph/health")
    async def graph_health_fallback():
        return {"status": "unavailable", "detail": "Graph routes failed to initialise"}

    app.include_router(_graph_fallback)


# ==========================================
# MISSION REPLAY ROUTES
# ==========================================

if _replay_routes_available:
    app.include_router(_replay_router, prefix="/api")
    logging.getLogger(__name__).info("Mission Replay routes registered at /api/mission-replay")
else:
    _replay_fallback = APIRouter()

    @_replay_fallback.get("/api/mission-replay/health")
    async def replay_health_fallback():
        return {"status": "unavailable", "detail": "Mission replay routes failed to initialise"}

    app.include_router(_replay_fallback)


# ==========================================
# ENTERPRISE REPLAY ROUTES
# ==========================================

if _enterprise_replay_routes_available:
    app.include_router(_enterprise_replay_router)
    logging.getLogger(__name__).info("Enterprise Replay routes registered at /api/enterprise-replay")
else:
    _enterprise_replay_fallback = APIRouter()

    @_enterprise_replay_fallback.get("/api/enterprise-replay/health")
    async def enterprise_replay_health_fallback():
        return {"status": "unavailable", "detail": "Enterprise replay routes failed to initialise"}

    app.include_router(_enterprise_replay_fallback)


# ==========================================
# MISSION LIBRARY ROUTES  (Enterprise Mission Templates)
# ==========================================

try:
    from backend.api.mission_library_routes import router as mission_library_router
    app.include_router(mission_library_router)
    logging.getLogger(__name__).info("Mission Library routes registered at /api/mission-library")
except Exception as _ml_err:
    _ml_fallback = APIRouter()

    @_ml_fallback.get("/api/mission-library/missions")
    async def mission_library_health_fallback():
        return {"missions": [], "total": 0, "status": "unavailable", "detail": str(_ml_err)}

    app.include_router(_ml_fallback)
    logging.getLogger(__name__).warning(f"Mission Library routes unavailable: {_ml_err}")


# ==========================================
# APPROVAL CENTER ROUTES  (Human Approval & Executive Control Center)
# ==========================================

try:
    from backend.api.approval_center_routes import router as approval_center_router
    app.include_router(approval_center_router)
    logging.getLogger(__name__).info("Approval Center routes registered at /api/approval-center")
except Exception as _ac_err:
    _ac_fallback = APIRouter()

    @_ac_fallback.get("/api/approval-center/policies")
    async def approval_center_health_fallback():
        return {"policies": [], "status": "unavailable", "detail": str(_ac_err)}

    app.include_router(_ac_fallback)
    logging.getLogger(__name__).warning(f"Approval Center routes unavailable: {_ac_err}")


# ==========================================
# SECURITY CENTER ROUTES  (Enterprise Security & Identity)
# ==========================================

try:
    from backend.api.security_center_routes import router as security_center_router
    app.include_router(security_center_router)
    logging.getLogger(__name__).info("Security Center routes registered at /api/security")
except Exception as _sc_err:
    _sc_fallback = APIRouter()

    @_sc_fallback.get("/api/security/status")
    async def security_center_health_fallback():
        return {"status": "unavailable", "detail": str(_sc_err)}

    app.include_router(_sc_fallback)
    logging.getLogger(__name__).warning(f"Security Center routes unavailable: {_sc_err}")


# ==========================================
# GOVERNANCE ROUTES
# ==========================================

try:
    from backend.api.governance_routes import router as governance_router
    app.include_router(governance_router)
    logging.getLogger(__name__).info("Governance routes registered")
except Exception as _gov_err:
    _gov_fallback = APIRouter()

    @_gov_fallback.get("/governance/health")
    async def governance_health_fallback():
        return {"status": "unavailable", "detail": str(_gov_err)}

    @_gov_fallback.get("/governance/queue")
    async def governance_queue_fallback():
        return {"requests": [], "total": 0, "detail": str(_gov_err)}

    @_gov_fallback.get("/governance/audit")
    async def governance_audit_fallback():
        return {"entries": [], "total": 0, "detail": str(_gov_err)}

    app.include_router(_gov_fallback)
    logging.getLogger(__name__).warning(f"Governance routes unavailable: {_gov_err}")


# ==========================================
# LIVE RESEARCH ROUTES
# ==========================================

try:
    from backend.api.research_routes import router as research_router
    app.include_router(research_router)
    logging.getLogger(__name__).info("Live Research routes registered")
except Exception as _research_err:
    _research_fallback = APIRouter()

    @_research_fallback.get("/api/research/health")
    async def research_fallback_health():
        return {"status": "unavailable", "detail": str(_research_err)}

    app.include_router(_research_fallback)
    logging.getLogger(__name__).warning(f"Research routes unavailable: {_research_err}")


# ==========================================
# COMPUTER AGENT ROUTES
# ==========================================

try:
    from backend.api.computer_routes import router as computer_router
    app.include_router(computer_router)
    logging.getLogger(__name__).info("Computer Agent routes registered")
except Exception as _computer_err:
    _computer_fallback = APIRouter()

    @_computer_fallback.get("/computer/health")
    async def computer_health_fallback():
        return {"status": "unavailable", "detail": str(_computer_err)}

    @_computer_fallback.get("/computer/status")
    async def computer_status_fallback():
        return {"status": "unavailable", "active_missions": 0, "detail": str(_computer_err)}

    @_computer_fallback.get("/computer/tasks")
    async def computer_tasks_fallback():
        return {"active_tasks": [], "completed_tasks": [], "total_completed": 0}

    app.include_router(_computer_fallback)
    logging.getLogger(__name__).warning(f"Computer Agent routes unavailable: {_computer_err}")


# ==========================================
# OPERATOR ROUTES  (Computer Agent V2)
# ==========================================

try:
    from backend.api.operator_routes import router as operator_router
    app.include_router(operator_router)
    logging.getLogger(__name__).info("Operator routes registered")
except Exception as _op_err:
    _op_fallback = APIRouter()

    @_op_fallback.get("/operator/health")
    async def operator_health_fallback():
        return {"status": "unavailable", "detail": str(_op_err)}

    @_op_fallback.get("/operator/active-missions")
    async def operator_active_fallback():
        return {"missions": [], "count": 0, "detail": str(_op_err)}

    app.include_router(_op_fallback)
    logging.getLogger(__name__).warning(f"Operator routes unavailable: {_op_err}")


# ==========================================
# WORKSPACE INTELLIGENCE ROUTES  (RAG)
# ==========================================

try:
    from backend.api.workspace_routes import router as workspace_router
    app.include_router(workspace_router)
    logging.getLogger(__name__).info("Workspace Intelligence routes registered")
except Exception as _ws_err:
    _ws_fallback = APIRouter()

    @_ws_fallback.get("/api/workspace/health")
    async def workspace_health_fallback():
        return {"status": "unavailable", "detail": str(_ws_err)}

    app.include_router(_ws_fallback)
    logging.getLogger(__name__).warning(f"Workspace routes unavailable: {_ws_err}")


# ==========================================
# VOICE V2 ROUTES  (LiveKit + Pipecat)
# ==========================================

try:
    from backend.voice_v2.voice_routes_v2 import router as voice_v2_router
    app.include_router(voice_v2_router)
    logging.getLogger(__name__).info("Voice V2 routes registered")
except Exception as _voice_v2_err:
    _voice_v2_fallback = APIRouter()

    @_voice_v2_fallback.get("/api/voice/v2/health")
    async def voice_v2_health_fallback():
        return {"status": "unavailable", "detail": str(_voice_v2_err)}

    app.include_router(_voice_v2_fallback)
    logging.getLogger(__name__).warning(f"Voice V2 routes unavailable: {_voice_v2_err}")


# ==========================================
# LLM ROUTER HEALTH ROUTES
# ==========================================

try:
    from backend.api.llm_health_routes import router as llm_health_router
    app.include_router(llm_health_router)
    logging.getLogger(__name__).info("LLM health routes registered at /health/llm")
except Exception as _llm_health_err:
    _llm_health_fallback = APIRouter()

    @_llm_health_fallback.get("/health/llm")
    async def llm_health_fallback():
        return {"status": "unavailable", "detail": str(_llm_health_err)}

    app.include_router(_llm_health_fallback)
    logging.getLogger(__name__).warning(f"LLM health routes unavailable: {_llm_health_err}")


# ==========================================
# SYSTEM HEALTH (aggregated)
# ==========================================

try:
    from backend.api.system_health_routes import router as system_health_router
    app.include_router(system_health_router)
    logging.getLogger(__name__).info("System health route registered at /health/system")
except Exception as _sys_health_err:
    _sys_health_fallback = APIRouter()

    @_sys_health_fallback.get("/health/system")
    async def system_health_fallback():
        return {"status": "unavailable", "detail": str(_sys_health_err)}

    app.include_router(_sys_health_fallback)
    logging.getLogger(__name__).warning(f"System health route unavailable: {_sys_health_err}")


# ==========================================
# PROMETHEUS METRICS + MIDDLEWARE
# ==========================================

try:
    from backend.api.metrics_routes import router as metrics_router, PrometheusMiddleware
    app.add_middleware(PrometheusMiddleware)
    app.include_router(metrics_router)
    logging.getLogger(__name__).info("Prometheus /metrics endpoint registered")
except Exception as _prom_err:
    logging.getLogger(__name__).warning(f"Prometheus metrics unavailable: {_prom_err}")


# ==========================================
# COST ENGINE ROUTES
# ==========================================

try:
    from backend.api.cost_routes import router as cost_router
    app.include_router(cost_router)
    logging.getLogger(__name__).info("Cost Engine routes registered at /api/costs")
except Exception as _cost_err:
    _cost_fallback = APIRouter()

    @_cost_fallback.get("/api/costs/summary")
    async def cost_summary_fallback():
        return {"error": str(_cost_err), "today_spend": 0.0, "month_spend": 0.0}

    app.include_router(_cost_fallback)
    logging.getLogger(__name__).warning(f"Cost Engine routes unavailable: {_cost_err}")


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
            "3.0.0"
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
    from backend.database.health    import check_database_health
    from backend.database.migrator  import get_migration_status

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
# EMBEDDING HEALTH
# ==========================================

@app.get("/health/embeddings")
async def embedding_health():
    from backend.memory.embedding_pipeline import embedding_pipeline, EMBED_DIM

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
    from backend.research.tavily_client      import tavily_client
    from backend.research.research_telemetry import research_telemetry

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


# ==========================================
# TEST EVENT
# ==========================================

from backend.events.event_models import CognitionEvent, EventTypes

@app.get("/test-event")

async def test_event():

    await event_bus.publish(

        CognitionEvent(

            agent="system",

            event_type=(

                EventTypes
                .EXECUTION_STARTED
            ),

            status="running",

            message=(

                "CortexPrime "
                "Cognitive Runtime Active"
            ),

            payload={

                "source":
                    "test-event-endpoint",

                "runtime":
                    "enterprise-cognitive-engine"
            }
        )
    )

    return {

        "status":
            "event_published"
    }


# ==========================================
# STARTUP EVENT
# ==========================================

@app.on_event("startup")

async def startup_event():

    print(
        "\nCortexPrime Runtime Initialized\n"
    )

    print(
        "Multi-Agent System Online"
    )

    print(
        "WebSocket Streaming Active"
    )

    print(
        "Runtime State Engine Active"
    )

    print(
        "Registered Agents:"
    )

    for agent in (

        agent_registry
        .list_agents()
    ):

        print(
            f"  - {agent}"
        )

    print()

    # ==========================================
    # STARTUP EVENT
    # ==========================================

    await event_bus.publish(

        CognitionEvent(

            agent="system",

            event_type=(

                EventTypes
                .EXECUTION_STARTED
            ),

            status="completed",

            message=(

                "CortexPrime Runtime Boot Complete"
            ),

            payload={

                "registered_agents":

                    agent_registry
                    .list_agents(),

                "runtime":
                    "initialized"
            }
        )
    )