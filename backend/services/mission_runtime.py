"""
Mission Runtime Service
=======================
Executes a complete autonomous mission:
  INIT → PLANNING → RESEARCHING → REASONING → VALIDATING → GENERATING → MEMORY_UPDATE → COMPLETED

Streams LLM tokens as WebSocket ``stream_chunk`` events so the frontend
receives the response incrementally without waiting for completion.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import AsyncGenerator, Dict, Any

from backend.events.event_bus import event_bus
from backend.events.event_models import CognitionEvent
from backend.llm.llm_gateway import llm_gateway
from backend.llm.llm_router  import llm_router, TaskType
from backend.memory.vector_memory import vector_memory
from backend.memory.memory_orchestrator import memory_orchestrator
from backend.services.memory_context_service import memory_context_service
from backend.runtime.runtime_state import runtime_state
from backend.websocket.connection_manager import manager
from backend.core.logging import get_logger, set_context, get_request_id

# Observability, Analytics, Cost, Governance integrations
from backend.observability.prometheus_metrics import metrics as _prom_metrics
from backend.analytics.cost_engine import cost_engine
from backend.runtime.runtime_metrics import runtime_metrics
from backend.orchestration.orchestration_tracer import orchestration_tracer

log = get_logger(__name__)

# =========================================================
# GUARDRAILS IMPORTS  (lazy to avoid circular imports)
# =========================================================

def _guardrails_check_input(objective: str):
    """
    Run NeMo Guardrails input check on the mission objective.
    Returns the GuardrailResult (never raises).
    """
    try:
        from backend.safety.guardrails_engine import guardrails_engine
        return guardrails_engine.check_input(objective)
    except Exception:
        return None


def _guardrails_check_output(text: str):
    """Run NeMo Guardrails output check on LLM response text."""
    try:
        from backend.safety.guardrails_engine import guardrails_engine
        return guardrails_engine.check_output(text)
    except Exception:
        return None


def _guardrails_check_tool(tool_name: str, action: str, url: str = ""):
    """Run NeMo Guardrails tool-call check."""
    try:
        from backend.safety.guardrails_engine import guardrails_engine
        return guardrails_engine.check_tool(tool_name, action, url)
    except Exception:
        return None


# =========================================================
# GOVERNANCE IMPORTS  (lazy to avoid circular imports)
# =========================================================

def _governance_assess(objective: str):
    try:
        from backend.safety.safety_guard import safety_guard
        return safety_guard.assess_action(action=objective, agent="orchestrator")
    except Exception:
        return None


async def _governance_request_approval(
    execution_id: str,
    objective:    str,
    risk_level:   str,
    reason:       str,
    session_id:   str | None,
):
    """Request human approval and await the decision."""
    from backend.safety.approval_queue import approval_queue
    from backend.safety.audit_logger   import audit_logger

    req = await approval_queue.request(
        execution_id = execution_id,
        agent        = "orchestrator",
        action       = "execute_mission",
        description  = f"Mission: {objective[:200]}",
        risk_level   = risk_level,
        context      = {"objective": objective, "reason": reason},
        session_id   = session_id,
        timeout      = 300,
    )

    audit_logger.log(
        execution_id = execution_id,
        agent        = "orchestrator",
        action       = "execute_mission",
        risk_level   = risk_level,
        outcome      = req.status.value,
        reason       = reason,
        session_id   = session_id,
        request_id   = req.request_id,
    )

    return req


def _governance_log(
    execution_id: str,
    agent:        str,
    action:       str,
    risk_level:   str,
    outcome:      str,
    reason:       str,
    session_id:   str | None = None,
) -> None:
    try:
        from backend.safety.audit_logger import audit_logger
        audit_logger.log(
            execution_id = execution_id,
            agent        = agent,
            action       = action,
            risk_level   = risk_level,
            outcome      = outcome,
            reason       = reason,
            session_id   = session_id,
        )
    except Exception:
        pass


def _is_emergency_stopped(execution_id: str) -> bool:
    try:
        from backend.safety.emergency_stop import emergency_stop
        return emergency_stop.is_stopped(execution_id)
    except Exception:
        return False


# =========================================================
# BROWSER TASK CLASSIFIER  (P7)
# =========================================================

# Keywords that signal the user wants a live browser action
_BROWSER_KEYWORDS = [
    "open ", "go to ", "visit ", "navigate to ", "browse to ",
    "open github", "open google", "open reddit", "open twitter",
    "open youtube", "open wikipedia", "open stackoverflow",
    "open linkedin", "open npm", "open pypi",
    "github.com", "google.com", "reddit.com",
    "https://", "http://",
    "search the web", "search online", "web search",
    "analyze this website", "analyze the website",
    "find pricing", "find on the web",
    "scrape", "extract from site",
]


def _is_browser_task(objective: str) -> bool:
    """
    Return True when the objective clearly requires a live browser action.
    Uses keyword matching — fast and deterministic; no extra LLM call needed.
    """
    obj_lower = objective.lower()
    return any(kw in obj_lower for kw in _BROWSER_KEYWORDS)


# =========================================================
# COMPUTER TASK CLASSIFIER  (Computer V2)
# =========================================================

_COMPUTER_KEYWORDS = [
    "open vscode", "open visual studio", "open notepad", "open calculator",
    "open folder", "open file", "open application", "open app",
    "launch ", "start application", "start app", "run application",
    "click on ", "click the ", "double click", "right click",
    "type into", "type in the", "type in field",
    "press enter", "press tab", "press escape",
    "desktop", "taskbar", "start menu", "system tray",
    "drag and drop", "resize window", "minimize window", "maximize window",
    "close window", "close application",
    "create file", "create folder", "rename file", "rename folder",
    "copy file", "move file", "delete file", "delete folder",
    "screenshot", "take a screenshot",
    "on the computer", "on my computer", "on the screen",
    "computer task", "automate the desktop",
]


def _is_computer_task(objective: str) -> bool:
    """
    Return True when the objective requires desktop / computer automation.
    Checked AFTER browser check so browser tasks are not misclassified.
    """
    obj_lower = objective.lower()
    return any(kw in obj_lower for kw in _COMPUTER_KEYWORDS)




# =========================================================
# MISSION STAGES
# =========================================================

class MissionStage:
    INIT         = "INIT"
    PLANNING     = "PLANNING"
    RESEARCHING  = "RESEARCHING"
    REASONING    = "REASONING"
    VALIDATING   = "VALIDATING"
    GENERATING   = "GENERATING"
    MEMORY_UPDATE= "MEMORY_UPDATE"
    COMPLETED    = "COMPLETED"
    FAILED       = "FAILED"


# =========================================================
# SYSTEM PROMPTS
# =========================================================

ORCHESTRATOR_SYSTEM = """You are CortexPrime, an autonomous multi-agent AI operating system.
You coordinate specialized agents (Planner, Research, Critic, Optimizer) to complete complex missions.
Respond with intelligence, depth, and precision. Provide actionable, well-structured answers."""

PLANNER_SYSTEM = """You are the CortexPrime Planner Agent.
Decompose the given objective into a clear execution plan with numbered steps.
Be concise. Focus on what needs to happen to answer the user's objective.
If memory context is provided, USE IT — incorporate known facts and past lessons."""

RESEARCHER_SYSTEM = """You are the CortexPrime Research Agent.
Synthesize relevant knowledge and context for the given query.
Draw on your training data to provide factual, well-sourced information.
If memory context or known facts are provided, build upon them rather than repeating."""

CRITIC_SYSTEM = """You are the CortexPrime Critic Agent.
Evaluate the research and plan. Identify gaps, validate claims, and assign a confidence score.
If past reflections are provided, apply the lessons learned in your critique.
Respond with: CONFIDENCE: X.XX (between 0.0 and 1.0) followed by your evaluation."""

RESPONSE_SYSTEM = """You are CortexPrime, a world-class autonomous AI with persistent memory.
You have completed a full multi-agent research and planning cycle.
You remember information from previous conversations — use it naturally without announcing it.
Synthesize the plan and research context into a comprehensive, well-structured response.
Be helpful, precise, and genuinely insightful. Use markdown formatting where appropriate."""


# =========================================================
# HELPER: EMIT COGNITION EVENT
# =========================================================

async def _emit(
    execution_id: str,
    agent:        str,
    event_type:   str,
    status:       str,
    message:      str,
    phase:        str = "",
    payload:      Dict[str, Any] | None = None,
    session_id:   str | None = None,
) -> None:
    await event_bus.publish(CognitionEvent(
        agent        = agent,
        event_type   = event_type,
        status       = status,
        phase        = phase or event_type,
        execution_id = execution_id,
        message      = message,
        payload      = payload or {},
        session_id   = session_id,
    ))


# =========================================================
# HELPER: SAFE LLM CALL WITH FALLBACK CHAIN
# =========================================================

# Map agent_type → TaskType for the multi-LLM router
_AGENT_TASK_MAP: Dict[str, TaskType] = {
    "planner":     TaskType.REASONING,
    "researcher":  TaskType.RESEARCH,
    "critic":      TaskType.REASONING,
    "optimizer":   TaskType.REASONING,
    "orchestrator":TaskType.CODING,
    "general":     TaskType.GENERAL,
    "runtime":     TaskType.GENERAL,
}


async def _call_llm(
    execution_id: str,
    prompt:       str,
    agent_type:   str,
    system:       str,
) -> str:
    """
    Route to the best available LLM provider via the multi-LLM router.
    Falls back automatically: Azure -> OpenAI -> Claude -> Gemini (order per task type).
    Records cost to CostEngine and metrics to Prometheus.
    """
    task_type = _AGENT_TASK_MAP.get(agent_type, TaskType.GENERAL)
    result    = await llm_router.route(
        prompt     = prompt,
        system     = system,
        task_type  = task_type,
        agent_type = agent_type,
    )
    if result.success:
        if result.fallback_count > 0:
            log.info(
                "_call_llm agent=%s task=%s used=%s after %d fallback(s) — tried: %s",
                agent_type, task_type.value, result.provider_used,
                result.fallback_count, result.tried_providers,
            )

        # Record to cost engine
        asyncio.ensure_future(cost_engine.record(
            provider=result.provider_used or "unknown",
            service="llm",
            model=result.model_used or "",
            prompt_tokens=result.prompt_tokens or 0,
            completion_tokens=result.completion_tokens or 0,
            mission_id=execution_id,
        ))

        # Record to Prometheus metrics
        _prom_metrics.record_llm_call(
            provider=result.provider_used or "unknown",
            model=result.model_used or "",
            latency_ms=result.latency_ms or 0,
            prompt_tokens=result.prompt_tokens or 0,
            completion_tokens=result.completion_tokens or 0,
            success=True,
        )

        # Record to runtime metrics
        runtime_metrics.register_token_usage(
            prompt_tokens=result.prompt_tokens or 0,
            completion_tokens=result.completion_tokens or 0,
        )

        return result.output

    log.error(
        "_call_llm all providers failed for agent=%s tried=%s",
        agent_type, result.tried_providers,
    )

    _prom_metrics.record_llm_call(
        provider=result.provider_used or "unknown",
        model=result.model_used or "",
        latency_ms=result.latency_ms or 0,
        success=False,
        error_type="all_providers_failed",
    )

    return ""


# =========================================================
# HELPER: STREAM LLM TOKENS OVER WEBSOCKET
# =========================================================

# =========================================================
# HELPER: SESSION-AWARE STREAM BROADCAST
# =========================================================

async def _send_stream_chunk(
    chunk: Dict[str, Any],
    session_id: str | None,
) -> None:
    """Send a stream chunk to the originating session only (or broadcast if no session)."""
    try:
        from backend.websocket.connection_pool import connection_pool
        if session_id and session_id != "global":
            sent = await connection_pool.broadcast_to_session(session_id, chunk)
            if sent == 0:
                # Session disconnected — broadcast globally as fallback
                await manager.broadcast(chunk)
        else:
            await connection_pool.broadcast(chunk)
    except Exception:
        await manager.broadcast(chunk)


# =========================================================
# HELPER: STREAM LLM TOKENS OVER WEBSOCKET
# =========================================================

async def _stream_llm_to_ws(
    execution_id: str,
    prompt:       str,
    system:       str,
    session_id:   str | None = None,
) -> str:
    """
    Stream tokens from OpenAI provider to the originating WS session.
    Returns the complete assembled text.
    """
    from backend.providers.openai_provider import openai_provider

    full_text = ""
    try:
        stream = await openai_provider.client.chat.completions.create(
            model    = openai_provider.deployment_name,
            messages = [
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            # temperature omitted — o-series reasoning models do not support it
            stream  = True,
            timeout = 90,
        )
        async for chunk in stream:
            try:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    token = delta.content
                    full_text += token
                    await _send_stream_chunk({
                        "agent":        "orchestrator",
                        "event_type":   "stream_chunk",
                        "stream":       True,
                        "stream_chunk": token,
                        "execution_id": execution_id,
                        "session_id":   session_id,
                        "status":       "streaming",
                        "message":      "Streaming response",
                    }, session_id)
                    await asyncio.sleep(0.005)
            except Exception:
                continue
    except Exception as stream_err:
        log.warning("Azure streaming failed: %s — falling back to bulk", stream_err)
        result = await llm_gateway.generate_azure(
            prompt        = prompt,
            agent_type    = "general",
            system_prompt = system,
        )
        if not result.get("success"):
            result = await llm_gateway.generate_openai(prompt=prompt, model="gpt-4o-mini")

        full_text = result.get("output", "")
        if full_text:
            words = full_text.split(" ")
            for i, word in enumerate(words):
                token = word + (" " if i < len(words) - 1 else "")
                await _send_stream_chunk({
                    "agent":        "orchestrator",
                    "event_type":   "stream_chunk",
                    "stream":       True,
                    "stream_chunk": token,
                    "execution_id": execution_id,
                    "session_id":   session_id,
                    "status":       "streaming",
                    "message":      "Streaming response",
                }, session_id)
                await asyncio.sleep(0.018)

    except Exception as e:
        log.error("Stream failed entirely: %s", e)
        full_text = f"I encountered an error generating the response: {str(e)}"

    # Signal stream end to the originating session
    await _send_stream_chunk({
        "agent":            "orchestrator",
        "event_type":       "stream_completed",
        "stream":           True,
        "stream_chunk":     "",
        "stream_completed": True,
        "execution_id":     execution_id,
        "session_id":       session_id,
        "status":           "completed",
        "message":          "Stream complete",
    }, session_id)

    return full_text


# =========================================================
# HELPER: STORE BROWSER MEMORY  (P8)
# =========================================================

async def _store_browser_memory(
    execution_id: str,
    session_id:   str,
    objective:    str,
    url:          str,
    title:        str,
    content:      str,
    history:      list,
) -> None:
    """
    Persist browser-visit data to the memory subsystem (P8).
    Stores: visited page, extracted content, action history, execution outcome.
    """
    try:
        vector_memory.store_memory(
            objective = f"[browser] {objective}",
            content   = {
                "url":     url,
                "title":   title,
                "content": content[:600],
                "history": history,
            },
            metadata  = {
                "execution_id": execution_id,
                "memory_type":  "browser_visit",
                "url":          url,
                "title":        title,
            },
        )
    except Exception as exc:
        log.warning("ChromaDB browser store failed: %s", exc)

    try:
        await memory_orchestrator.store_cognition_event(
            agent      = "browser_agent",
            event_type = "browser_visit",
            content    = f"Visited {url} ({title}): {content[:400]}",
            session_id = session_id,
            mission_id = execution_id,
            metadata   = {
                "url":          url,
                "title":        title,
                "content_len":  len(content),
                "page_history": history,
            },
        )
    except Exception as exc:
        log.warning("Episodic browser store failed: %s", exc)


# =========================================================
# MISSION RUNTIME SERVICE
# =========================================================

class MissionRuntimeService:

    # ─────────────────────────────────────────────────────
    # PUBLIC ENTRY POINT
    # ─────────────────────────────────────────────────────

    async def execute_mission(
        self,
        objective:     str,
        session_id:    str | None = None,
        workspace_id:  str | None = None,
        voice_context: str | None = None,
    ) -> Dict[str, Any]:
        """
        Run a complete mission pipeline and stream the final response.
        session_id   routes stream events to the originating client only.
        workspace_id enables document RAG context injection.
        voice_context is the formatted multi-turn conversation history from
                      VoiceSession.last_n_turns(); injected into planner and
                      response prompts so the LLM has conversational continuity.
        Returns a summary dict after completion.
        """
        execution_id = str(uuid.uuid4())
        started_at   = datetime.utcnow().isoformat()

        # ── Propagate request_id + mission_id into logging / Sentry context ──
        set_context(mission_id=execution_id, session_id=session_id or "global")
        try:
            import sentry_sdk
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("mission_id",  execution_id)
                scope.set_tag("request_id",  get_request_id())
                scope.set_tag("session_id",  session_id or "global")
                scope.set_context("mission", {
                    "execution_id": execution_id,
                    "request_id":   get_request_id(),
                    "session_id":   session_id or "global",
                    "objective":    objective[:200],
                })
        except Exception:
            pass

        log.info("Mission started | %s | session=%s | workspace=%s | %s",
                 execution_id[:8], session_id or "global",
                 workspace_id or "none", objective[:60])

        # -- OBSERVABILITY: trace mission start --
        _mission_span = None
        try:
            _mission_span = orchestration_tracer.start_span(
                execution_id=execution_id,
                agent="orchestrator",
                stage="mission_start",
                metadata={"objective": objective[:200]},
            )
        except Exception:
            pass

        # -- PROMETHEUS: active mission gauge --
        try:
            _prom_metrics.missions_started.labels(mission_type="autonomous").inc()
            _prom_metrics.active_missions.inc()
        except Exception:
            pass

        # -- AUDIT: MISSION STARTED --
        _governance_log(
            execution_id, "orchestrator", "mission_start",
            "low", "started", f"Mission started: {objective[:120]}",
            session_id,
        )

        # ── GOVERNANCE: RISK ANALYSIS ─────────────────────
        assessment = _governance_assess(objective)
        if assessment:
            risk = assessment.risk_level.value
            log.info("Risk assessment: %s — %s", risk, assessment.reason)

            if assessment.blocked:
                # Hard block — never execute
                _governance_log(
                    execution_id, "orchestrator", "execute_mission",
                    risk, "blocked", assessment.reason, session_id,
                )
                await _emit(
                    execution_id, "governance", "mission_blocked", "failed",
                    f"Mission blocked by safety guard: {assessment.reason}",
                    MissionStage.INIT,
                    {"risk_level": risk, "reason": assessment.reason},
                    session_id,
                )
                await _send_stream_chunk({
                    "agent":            "governance",
                    "event_type":       "stream_completed",
                    "stream_completed": True,
                    "execution_id":     execution_id,
                    "session_id":       session_id,
                    "status":           "blocked",
                    "message":          f"Mission blocked: {assessment.reason}",
                }, session_id)
                return {
                    "status":       "blocked",
                    "execution_id": execution_id,
                    "reason":       assessment.reason,
                    "risk_level":   risk,
                }

            if assessment.requires_approval:
                # Pause and request human approval
                await _emit(
                    execution_id, "governance", "approval_requested", "info",
                    f"Mission paused — human approval required (risk={risk})",
                    MissionStage.INIT,
                    {
                        "risk_level":    risk,
                        "reason":        assessment.reason,
                        "objective":     objective[:200],
                    },
                    session_id,
                )
                # Notify frontend: stream_chunk with governance context
                await _send_stream_chunk({
                    "agent":            "governance",
                    "event_type":       "mission_paused",
                    "governance":       True,
                    "risk_level":       risk,
                    "requires_approval": True,
                    "execution_id":     execution_id,
                    "session_id":       session_id,
                    "status":           "pending_approval",
                    "message":          f"⏳ Approval required before execution (risk={risk}): {assessment.reason}",
                }, session_id)

                approval_req = await _governance_request_approval(
                    execution_id = execution_id,
                    objective    = objective,
                    risk_level   = risk,
                    reason       = assessment.reason,
                    session_id   = session_id,
                )

                if approval_req.status.value != "approved":
                    # Rejected or timed out
                    reject_reason = approval_req.reject_reason or "Approval not granted"
                    await _emit(
                        execution_id, "governance", "mission_rejected", "failed",
                        f"Mission rejected: {reject_reason}",
                        MissionStage.FAILED,
                        {"reason": reject_reason},
                        session_id,
                    )
                    await _send_stream_chunk({
                        "agent":            "governance",
                        "event_type":       "stream_completed",
                        "stream_completed": True,
                        "execution_id":     execution_id,
                        "session_id":       session_id,
                        "status":           "rejected",
                        "message":          f"Mission rejected: {reject_reason}",
                    }, session_id)
                    return {
                        "status":       "rejected",
                        "execution_id": execution_id,
                        "reason":       reject_reason,
                        "risk_level":   risk,
                    }

                # Approved — resume
                await _emit(
                    execution_id, "governance", "mission_approved", "info",
                    "Mission approved — resuming execution",
                    MissionStage.INIT,
                    {"approved_by": approval_req.resolved_by},
                    session_id,
                )
                await _send_stream_chunk({
                    "agent":        "governance",
                    "event_type":   "mission_resumed",
                    "governance":   True,
                    "execution_id": execution_id,
                    "session_id":   session_id,
                    "status":       "approved",
                    "message":      "✅ Approved — mission execution resumed.",
                }, session_id)

            else:
                # Low/medium — log and continue
                _governance_log(
                    execution_id, "orchestrator", "execute_mission",
                    risk, "allowed", assessment.reason, session_id,
                )

        # ── EMERGENCY STOP CHECK ──────────────────────────
        if _is_emergency_stopped(execution_id):
            return {"status": "stopped", "execution_id": execution_id,
                    "reason": "Emergency stop active"}

        try:
            result = await self._run_pipeline(
                execution_id, objective, session_id, workspace_id,
                voice_context=voice_context,
            )
            # ── AUDIT: MISSION COMPLETED ──────────────────
            _governance_log(
                execution_id, "orchestrator", "mission_complete",
                "low", "completed",
                f"Mission completed: {objective[:120]}",
                session_id,
            )
            return result
        except Exception as exc:
            log.error("Mission failed: %s", exc)
            # -- PROMETHEUS: record failure --
            try:
                _prom_metrics.missions_failed.labels(
                    mission_type="autonomous", error_type=type(exc).__name__
                ).inc()
                _prom_metrics.active_missions.dec()
            except Exception:
                pass
            # -- GOVERNANCE: AUDIT: MISSION FAILED --
            _governance_log(
                execution_id, "orchestrator", "mission_failure",
                "high", "failed",
                f"Mission failed with exception: {str(exc)[:256]}",
                session_id,
            )
            await _emit(execution_id, "orchestrator", "mission_failed", "failed",
                        f"Mission failed: {exc}", MissionStage.FAILED,
                        session_id=session_id)
            await _send_stream_chunk({
                "agent":            "orchestrator",
                "event_type":       "stream_completed",
                "stream_completed": True,
                "execution_id":     execution_id,
                "session_id":       session_id,
                "status":           "failed",
                "message":          str(exc),
            }, session_id)
            return {"status": "failed", "execution_id": execution_id, "error": str(exc)}

    # ─────────────────────────────────────────────────────
    # PIPELINE
    # ─────────────────────────────────────────────────────

    async def _run_pipeline(
        self,
        execution_id:  str,
        objective:     str,
        session_id:    str | None = None,
        workspace_id:  str | None = None,
        voice_context: str | None = None,
    ) -> Dict[str, Any]:

        # ── NEMO GUARDRAILS: input check ──────────────────
        _gr = _guardrails_check_input(objective)
        if _gr is not None and _gr.blocked:
            log.warning(
                "GUARDRAILS BLOCKED mission | exec=%s rule=%s",
                execution_id, _gr.matched_rule,
            )
            await _emit(
                execution_id, "guardrails", "mission_blocked", "blocked",
                f"Mission blocked by guardrails: {_gr.reason}",
                MissionStage.INIT,
                _gr.to_dict(),
                session_id,
            )
            return {
                "execution_id":  execution_id,
                "status":        "blocked",
                "blocked":       True,
                "reason":        _gr.reason,
                "violation_type": _gr.violation_type.value if _gr.violation_type else None,
                "rule":          _gr.matched_rule,
            }

        # ── INIT ──────────────────────────────────────────
        await _emit(execution_id, "orchestrator", "mission_created", "running",
                    f"Mission created: {objective[:80]}", MissionStage.INIT,
                    {"objective": objective}, session_id)

        runtime_state.start_execution(execution_id=execution_id, objective=objective)

        # ── BROWSER AGENT  (P2 / P7) ──────────────────────
        # When the objective requires a live browser action, run the browser
        # agent first and inject the extracted content into the pipeline.
        browser_context_text = ""
        browser_result:      Dict[str, Any] = {}

        if _is_browser_task(objective):
            await _emit(
                execution_id, "browser_agent", "browser_task_started", "running",
                "Browser agent activated — executing live web action",
                MissionStage.RESEARCHING,
                {"objective": objective},
                session_id,
            )
            try:
                from backend.tools.browser_agent import browser_agent
                # Guardrails: validate browser action before dispatch
                _br_gr = _guardrails_check_tool("browser", objective)
                _browser_blocked = _br_gr is not None and _br_gr.blocked
                if _browser_blocked:
                    log.warning("GUARDRAILS blocked browser task | rule=%s", _br_gr.matched_rule)
                    await _emit(
                        execution_id, "guardrails", "browser_blocked", "blocked",
                        f"Browser task blocked: {_br_gr.reason}",
                        MissionStage.RESEARCHING, _br_gr.to_dict(), session_id,
                    )
                    browser_result = {"success": False, "error": _br_gr.reason, "blocked": True}
                if not _browser_blocked:
                    browser_result = await browser_agent.execute_task(
                        execution_id = execution_id,
                        objective    = objective,
                        session_id   = execution_id,   # one browser context per mission
                    )
                if browser_result.get("success"):
                    title   = browser_result.get("title", "")
                    url     = browser_result.get("url", "")
                    content = browser_result.get("extracted_text", "")
                    browser_context_text = (
                        f"## Browser Result\n"
                        f"**URL:** {url}\n"
                        f"**Title:** {title}\n\n"
                        f"**Extracted Content:**\n{content}"
                    )
                    await _emit(
                        execution_id, "browser_agent", "browser_task_completed", "completed",
                        f"Browser extracted {len(content)} chars from: {title}",
                        MissionStage.RESEARCHING,
                        {"url": url, "title": title, "content_length": len(content)},
                        session_id,
                    )
                    log.info("Browser agent: %d chars from %s", len(content), url)

                    # ── MEMORY: store browser visit (P8) ──────────
                    asyncio.ensure_future(
                        _store_browser_memory(
                            execution_id = execution_id,
                            session_id   = session_id or "global",
                            objective    = objective,
                            url          = url,
                            title        = title,
                            content      = content,
                            history      = browser_agent.get_session_history(execution_id),
                        )
                    )
                else:
                    log.warning("Browser agent returned failure: %s", browser_result.get("error"))

            except Exception as browser_err:
                log.warning("Browser agent step failed: %s", browser_err)
            finally:
                # Close the per-mission browser session
                try:
                    from backend.tools.browser_agent import browser_agent as _ba
                    await _ba.close_session(execution_id)
                except Exception:
                    pass

        # ── COMPUTER AGENT V2  (autonomous desktop) ───────
        computer_context_text = ""
        computer_result: Dict[str, Any] = {}

        if not _is_browser_task(objective) and _is_computer_task(objective):
            await _emit(
                execution_id, "computer_agent_v2", "computer_task_started", "running",
                "Computer Agent V2 activated — autonomous desktop execution",
                MissionStage.RESEARCHING,
                {"objective": objective},
                session_id,
            )
            try:
                from backend.computer.computer_agent_v2 import computer_agent_v2
                computer_result = await computer_agent_v2.execute_autonomous_mission({
                    "goal":          objective,
                    "execution_id":  execution_id,
                    "session_id":    session_id,
                    "max_iterations": 20,
                    "use_vision":    True,
                })
                if computer_result.get("success"):
                    summary  = computer_result.get("summary", "")
                    steps    = computer_result.get("step_count", 0)
                    computer_context_text = (
                        f"## Computer Agent Result\n"
                        f"**Status:** {computer_result.get('status', 'completed')}\n"
                        f"**Steps executed:** {steps}\n\n"
                        f"**Summary:** {summary}"
                    )
                    await _emit(
                        execution_id, "computer_agent_v2", "computer_task_completed", "completed",
                        f"Computer task done: {steps} steps — {summary[:80]}",
                        MissionStage.RESEARCHING,
                        computer_result,
                        session_id,
                    )
                else:
                    log.warning("Computer agent returned failure: %s", computer_result.get("error"))

            except Exception as computer_err:
                log.warning("Computer agent step failed: %s", computer_err)

        # ── EMERGENCY STOP CHECK (mid-pipeline) ───────────
        if _is_emergency_stopped(execution_id):
            await _emit(execution_id, "governance", "mission_stopped", "failed",
                        "Mission halted — emergency stop active",
                        MissionStage.FAILED, session_id=session_id)
            return {"status": "stopped", "execution_id": execution_id,
                    "reason": "Emergency stop activated"}

        # Extract user-stated facts (e.g. "my project is CortexPrime") before retrieval
        asyncio.ensure_future(
            memory_context_service.extract_and_store_facts(
                text       = objective,
                session_id = session_id or "global",
                source     = "mission_objective",
            )
        )

        # ── MEMORY RETRIEVAL (full memory system) ─────────
        mem_ctx = None
        try:
            mem_ctx = await memory_context_service.retrieve_for_mission(
                objective      = objective,
                session_id     = session_id or "global",
                execution_id   = execution_id,
                ws_session_id  = session_id,
            )
            log.info("Memory retrieved: %s", mem_ctx.summary_line())
        except Exception as mem_err:
            log.warning("Memory retrieval failed: %s — proceeding without context", mem_err)

        # Build the memory context strings for agent prompts
        memory_context    = mem_ctx.full_context      if mem_ctx and mem_ctx.has_context else "No prior memory context."
        planner_memory    = mem_ctx.planner_injection  if mem_ctx and mem_ctx.has_context else ""
        researcher_memory = mem_ctx.researcher_injection if mem_ctx and mem_ctx.has_context else ""
        critic_memory     = mem_ctx.critic_injection   if mem_ctx and mem_ctx.has_context else ""

        # ── WORKSPACE DOCUMENT RETRIEVAL ──────────────────
        workspace_context = ""
        if workspace_id:
            try:
                from backend.workspace.retrieval_service import retrieval_service
                ws_ctx = await retrieval_service.retrieve(
                    workspace_id = workspace_id,
                    query        = objective,
                    n_chunks     = 6,
                )
                if ws_ctx.has_context:
                    workspace_context = ws_ctx.formatted
                    await _emit(
                        execution_id, "memory", "workspace_context_loaded", "info",
                        f"Loaded {len(ws_ctx.chunks)} document chunks from workspace",
                        MissionStage.INIT,
                        {"chunks": len(ws_ctx.chunks), "workspace": workspace_id},
                        session_id,
                    )
                    log.info("Workspace RAG: %d chunks loaded from workspace %s",
                             len(ws_ctx.chunks), workspace_id)
            except Exception as ws_err:
                log.warning("Workspace retrieval failed: %s", ws_err)

        # ── PLANNING ──────────────────────────────────────
        await _emit(execution_id, "planner", "planning_started", "running",
                    "Planner activated — decomposing objective", MissionStage.PLANNING,
                    session_id=session_id)

        runtime_state.update_agent_state("planner", "running")

        planner_prompt = f"Objective: {objective}"
        if voice_context:
            planner_prompt = (
                f"{voice_context}\n\n"
                f"Current request: {objective}"
            )
        if planner_memory:
            planner_prompt += f"\n\nMemory context:\n{planner_memory}"
        if browser_context_text:
            planner_prompt += f"\n\n{browser_context_text}"
        if computer_context_text:
            planner_prompt += f"\n\n{computer_context_text}"
        if workspace_context:
            planner_prompt += f"\n\n{workspace_context}"

        plan_text = await _call_llm(
            execution_id = execution_id,
            prompt       = planner_prompt,
            agent_type   = "planner",
            system       = PLANNER_SYSTEM,
        )
        if not plan_text:
            plan_text = f"Plan for: {objective}\n1. Research background\n2. Analyze key factors\n3. Synthesize response\n4. Validate accuracy"

        runtime_state.update_agent_state("planner", "completed")
        await _emit(execution_id, "planner", "planning_completed", "completed",
                    "Execution plan ready", MissionStage.PLANNING,
                    {"plan_preview": plan_text[:200]},
                    session_id)

        # ── RESEARCH ──────────────────────────────────────
        await _emit(execution_id, "research", "research_started", "running",
                    "Research agent activated — gathering context", MissionStage.RESEARCHING,
                    session_id=session_id)

        runtime_state.update_agent_state("research", "running")

        researcher_prompt = (
            f"Research the following objective comprehensively:\n{objective}\n\n"
            f"Execution plan:\n{plan_text[:500]}"
        )
        if browser_context_text:
            researcher_prompt += f"\n\nLive browser data (use this as primary source):\n{browser_context_text}"
        if computer_context_text:
            researcher_prompt += f"\n\nComputer agent execution result:\n{computer_context_text}"
        if researcher_memory:
            researcher_prompt += f"\n\nMemory context:\n{researcher_memory}"
        if workspace_context:
            researcher_prompt += f"\n\n{workspace_context}"

        research_text = await _call_llm(
            execution_id = execution_id,
            prompt       = researcher_prompt,
            agent_type   = "runtime",
            system       = RESEARCHER_SYSTEM,
        )
        if not research_text:
            research_text = f"Research findings for: {objective}"

        runtime_state.update_agent_state("research", "completed")
        await _emit(execution_id, "research", "research_completed", "completed",
                    "Research phase complete", MissionStage.RESEARCHING,
                    {"research_preview": research_text[:200]},
                    session_id)

        # ── REASONING / CRITIQUE ──────────────────────────
        await _emit(execution_id, "critic", "critic_started", "running",
                    "Critic validating research quality and confidence", MissionStage.VALIDATING,
                    session_id=session_id)

        runtime_state.update_agent_state("critic", "running")

        critic_prompt = (
            f"Evaluate this research for the objective: '{objective}'\n\n"
            f"Research:\n{research_text[:800]}"
        )
        if critic_memory:
            critic_prompt += f"\n\nPast reflections to consider:\n{critic_memory}"
        if workspace_context:
            critic_prompt += f"\n\n{workspace_context}"

        critic_text = await _call_llm(
            execution_id = execution_id,
            prompt       = critic_prompt,
            agent_type   = "critic",
            system       = CRITIC_SYSTEM,
        )

        # Parse confidence score from critic output
        confidence = 0.88
        try:
            import re
            m = re.search(r"CONFIDENCE:\s*([\d.]+)", critic_text or "")
            if m:
                confidence = min(1.0, max(0.0, float(m.group(1))))
        except Exception:
            pass

        runtime_state.update_agent_state("critic", "completed")
        await _emit(execution_id, "critic", "critic_completed", "completed",
                    f"Validation complete — confidence: {confidence:.2f}",
                    MissionStage.VALIDATING,
                    {"confidence_score": confidence, "hallucination_score": 1 - confidence},
                    session_id)

        # ── GENERATING (STREAMING) ────────────────────────
        await _emit(execution_id, "orchestrator", "generating_response", "running",
                    "Generating final response — streaming to client",
                    MissionStage.GENERATING,
                    session_id=session_id)

        runtime_state.update_agent_state("orchestrator", "running")

        response_prompt = (
            f"Objective: {objective}\n\n"
            f"Execution plan:\n{plan_text[:600]}\n\n"
            f"Research findings:\n{research_text[:1000]}\n\n"
        )
        if browser_context_text:
            response_prompt += (
                f"Live browser data (use as primary factual source):\n"
                f"{browser_context_text[:3000]}\n\n"
            )
        if computer_context_text:
            response_prompt += (
                f"Computer agent execution result:\n"
                f"{computer_context_text[:2000]}\n\n"
            )
        if workspace_context:
            response_prompt += (
                f"{workspace_context[:2000]}\n\n"
                "IMPORTANT: Cite sources using the [N] markers when using information "
                "from the documents above.\n\n"
            )
        if voice_context:
            response_prompt += (
                f"{voice_context}\n\n"
                f"Current request: {objective}\n\n"
            )
        if memory_context and memory_context != "No prior memory context.":
            response_prompt += f"Memory context (use naturally):\n{memory_context[:600]}\n\n"
        response_prompt += (
            "Synthesize all of the above into a comprehensive, well-structured response. "
            "Use markdown formatting. Be genuinely helpful and insightful."
        )

        # STREAM tokens to the originating session
        final_response = await _stream_llm_to_ws(
            execution_id = execution_id,
            prompt       = response_prompt,
            system       = RESPONSE_SYSTEM,
            session_id   = session_id,
        )

        # ── NEMO GUARDRAILS: output check ─────────────────
        if final_response:
            _out_gr = _guardrails_check_output(final_response)
            if _out_gr is not None and _out_gr.blocked:
                log.warning(
                    "GUARDRAILS blocked LLM output | exec=%s rule=%s",
                    execution_id, _out_gr.matched_rule,
                )
                final_response = (
                    "I'm unable to provide that response as it was flagged by the "
                    "content safety layer. Please rephrase your request."
                )
            elif _out_gr is not None and _out_gr.decision.value == "warn" and _out_gr.sanitized:
                log.info(
                    "GUARDRAILS sanitized output | exec=%s rule=%s",
                    execution_id, _out_gr.matched_rule,
                )
                final_response = _out_gr.sanitized

        if not final_response:
            final_response = (
                f"**Analysis: {objective}**\n\n"
                f"{research_text}\n\n"
                f"**Execution Plan:**\n{plan_text}"
            )

        runtime_state.update_agent_state("orchestrator", "completed")

        # ── MEMORY UPDATE ─────────────────────────────────
        await _emit(execution_id, "memory", "memory_update_started", "running",
                    "Storing mission to memory", MissionStage.MEMORY_UPDATE,
                    session_id=session_id)

        # ChromaDB store (fast, sync, for immediate retrieval)
        try:
            vector_memory.store_memory(
                objective = objective,
                content   = {
                    "response":      final_response[:500],
                    "plan":          plan_text[:300],
                    "research":      research_text[:300],
                    "confidence":    confidence,
                    "browser_url":   browser_result.get("url", ""),
                    "browser_title": browser_result.get("title", ""),
                },
                metadata  = {
                    "execution_id":  execution_id,
                    "status":        "completed",
                    "confidence":    confidence,
                    "has_browser":   bool(browser_result.get("success")),
                }
            )
        except Exception as store_err:
            log.warning("ChromaDB store failed: %s", store_err)

        # Full memory lifecycle via MemoryContextService
        # (episodic + semantic + reflection — all non-fatal)
        asyncio.ensure_future(
            memory_context_service.store_mission_result(
                objective     = objective,
                response      = final_response,
                execution_id  = execution_id,
                session_id    = session_id or "global",
                confidence    = confidence,
                plan_text     = plan_text,
                research_text = research_text,
            )
        )
        asyncio.ensure_future(
            memory_context_service.generate_and_store_reflection(
                objective      = objective,
                response       = final_response,
                plan_text      = plan_text,
                research_text  = research_text,
                confidence     = confidence,
                execution_id   = execution_id,
                session_id     = session_id or "global",
                ws_session_id  = session_id,
            )
        )

        await _emit(execution_id, "memory", "memory_updated", "completed",
                    "Mission stored to memory", MissionStage.MEMORY_UPDATE,
                    session_id=session_id)

        # -- GOVERNANCE: record mission completion --
        _governance_log(
            execution_id, "orchestrator", "mission_complete",
            "low", "completed", f"Mission completed: {objective[:120]}",
            session_id,
        )

        # -- OBSERVABILITY: trace final span --
        if _mission_span is not None:
            try:
                orchestration_tracer.finish_span(
                    span=_mission_span,
                    status="completed",
                )
            except Exception:
                pass

        # -- ANALYTICS: record to cost engine for mission summary --
        try:
            asyncio.ensure_future(cost_engine.record(
                provider="mission_runtime",
                service="mission_execution",
                model="",
                mission_id=execution_id,
                extra={
                    "objective": objective[:200],
                    "confidence": confidence,
                    "has_browser": bool(browser_result.get("success")),
                    "response_length": len(final_response),
                },
            ))
        except Exception:
            pass

        # -- NEO4J: record execution graph node --
        try:
            from backend.infrastructure.neo4j.connection import neo4j_connection as _nc
            if _nc.is_available:
                from backend.infrastructure.neo4j.graph_manager import neo4j_graph
                asyncio.ensure_future(neo4j_graph.complete_execution(
                    execution_id=execution_id,
                    status="completed",
                    confidence=confidence,
                ))
        except Exception:
            pass

        # -- PROMETHEUS: record mission metrics --
        try:
            _prom_metrics.missions_completed.labels(mission_type="autonomous").inc()
            _prom_metrics.active_missions.dec()
        except Exception:
            pass

        # -- COMPLETED --
        await _emit(execution_id, "orchestrator", "mission_completed", "completed",
                    f"Mission complete: {objective[:60]}",
                    MissionStage.COMPLETED,
                    {
                        "execution_id":     execution_id,
                        "confidence_score": confidence,
                        "objective":        objective,
                    },
                    session_id)

        runtime_state.complete_execution(execution_id)

        log.info("✅ Mission complete | %s | confidence=%.2f", execution_id[:8], confidence)

        return {
            "status":           "completed",
            "execution_id":     execution_id,
            "objective":        objective,
            "confidence_score": confidence,
            "response":         final_response,
            "response_length":  len(final_response),
        }


# =========================================================
# SINGLETON
# =========================================================

mission_runtime = MissionRuntimeService()
