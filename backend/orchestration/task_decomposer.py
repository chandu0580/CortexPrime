from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# =========================================================
# SUBTASK
# =========================================================

class SubTask:
    """A single unit of work within a decomposed execution plan."""

    def __init__(
        self,
        task_id:      str,
        step:         int,
        agent:        str,
        action:       str,
        input_data:   Dict[str, Any],
        depends_on:   List[str] = [],
        priority:     int = 5,
        execution_id: str = "",
    ):
        self.task_id      = task_id
        self.step         = step
        self.agent        = agent
        self.action       = action
        self.input_data   = input_data
        self.depends_on   = depends_on
        self.priority     = priority
        self.execution_id = execution_id
        self.status       = "pending"      # pending / running / completed / failed
        self.result:      Optional[Dict[str, Any]] = None
        self.created_at   = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id":      self.task_id,
            "step":         self.step,
            "agent":        self.agent,
            "action":       self.action,
            "input_data":   self.input_data,
            "depends_on":   self.depends_on,
            "priority":     self.priority,
            "execution_id": self.execution_id,
            "status":       self.status,
        }


# =========================================================
# TASK DECOMPOSER
# =========================================================

class TaskDecomposer:
    """
    Breaks an objective into an ordered list of SubTasks that map
    to the CortexPrime cognition pipeline:

    Orchestrator → Planner → Research → Critic → Optimizer → Reflection → Memory

    For complex objectives the LLM gateway is used to dynamically
    decompose tasks. For standard objectives a deterministic
    pipeline template is applied.
    """

    PIPELINE_TEMPLATE = [
        # (step, agent, action, depends_on)
        (1, "planner",    "decompose_objective",  []),
        (2, "research",   "gather_intelligence",  ["planner"]),
        (3, "critic",     "validate_findings",    ["research"]),
        (4, "optimizer",  "optimize_strategy",    ["critic"]),
        (5, "reflection", "reflect_on_execution", ["optimizer"]),
        (6, "memory",     "persist_execution",    ["reflection"]),
    ]

    # ---------------------------------------------------------
    # DECOMPOSE
    # ---------------------------------------------------------

    async def decompose(
        self,
        execution_id: str,
        objective:    str,
        priority:     int = 5,
        use_llm:      bool = False,
    ) -> List[SubTask]:
        """
        Returns an ordered list of SubTasks for the objective.
        When use_llm=True, the LLM gateway is consulted for
        dynamic decomposition; otherwise the pipeline template is used.
        """
        if use_llm:
            try:
                return await self._llm_decompose(
                    execution_id, objective, priority
                )
            except Exception as exc:
                log.warning(
                    "LLM decomposition failed, falling back to template: %s", exc
                )

        return self._template_decompose(execution_id, objective, priority)

    # ---------------------------------------------------------
    # TEMPLATE DECOMPOSITION
    # ---------------------------------------------------------

    def _template_decompose(
        self,
        execution_id: str,
        objective:    str,
        priority:     int,
    ) -> List[SubTask]:
        tasks: List[SubTask] = []

        for step, agent, action, depends_on in self.PIPELINE_TEMPLATE:
            task_id = f"{execution_id}::{agent}::{step}"
            dep_ids = [
                f"{execution_id}::{dep}::{i+1}"
                for i, (_, dep, _, _) in enumerate(self.PIPELINE_TEMPLATE)
                if dep in depends_on
            ]

            input_data: Dict[str, Any] = {"objective": objective}

            if agent == "research":
                input_data["query"] = objective

            elif agent == "critic":
                input_data["response"] = ""  # filled at runtime

            elif agent == "optimizer":
                input_data["content"]  = ""  # filled at runtime

            elif agent == "reflection":
                input_data["execution_id"] = execution_id
                input_data["result"]       = {}

            elif agent == "memory":
                input_data["content"]      = objective
                input_data["execution_id"] = execution_id

            tasks.append(
                SubTask(
                    task_id=task_id,
                    step=step,
                    agent=agent,
                    action=action,
                    input_data=input_data,
                    depends_on=dep_ids,
                    priority=priority,
                    execution_id=execution_id,
                )
            )

        return tasks

    # ---------------------------------------------------------
    # LLM DECOMPOSITION
    # ---------------------------------------------------------

    async def _llm_decompose(
        self,
        execution_id: str,
        objective:    str,
        priority:     int,
    ) -> List[SubTask]:
        from backend.llm.llm_gateway import llm_gateway

        prompt = f"""You are a cognitive task decomposer for an autonomous AI system.

Given the following objective, decompose it into an ordered list of subtasks.
Each subtask must map to one of these agents: planner, research, critic, optimizer, reflection, memory.

Objective: {objective}

Return a JSON array with objects having:
- step: integer (order of execution)
- agent: one of [planner, research, critic, optimizer, reflection, memory]
- action: short description of what the agent should do
- input_key: the primary input field name (e.g. 'objective', 'query', 'response')
- input_value: the value for that input field

Respond ONLY with valid JSON array, no markdown."""

        response = await llm_gateway.complete(
            prompt=prompt,
            system="You are a precise task decomposition engine. Respond with JSON only.",
            max_tokens=1000,
        )

        import json
        import re

        raw = response.get("content", "")
        # Extract JSON array from response
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            raise ValueError("No JSON array in LLM decomposition response")

        steps = json.loads(match.group(0))
        tasks: List[SubTask] = []

        prev_agent = None
        for item in steps:
            step       = item.get("step", len(tasks) + 1)
            agent      = item.get("agent", "planner")
            action     = item.get("action", "execute")
            input_key  = item.get("input_key", "objective")
            input_val  = item.get("input_value", objective)

            dep_ids = []
            if prev_agent:
                dep_ids = [f"{execution_id}::{prev_agent}::{step-1}"]

            task_id = f"{execution_id}::{agent}::{step}"

            tasks.append(
                SubTask(
                    task_id=task_id,
                    step=step,
                    agent=agent,
                    action=action,
                    input_data={input_key: input_val, "objective": objective},
                    depends_on=dep_ids,
                    priority=priority,
                    execution_id=execution_id,
                )
            )
            prev_agent = agent

        return tasks


# =========================================================
# SINGLETON
# =========================================================

task_decomposer = TaskDecomposer()
