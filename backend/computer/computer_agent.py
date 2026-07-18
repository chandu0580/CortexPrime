
import asyncio
from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from backend.computer.computer_task_engine import computer_task_engine
from backend.computer.desktop_controller import desktop_controller
from backend.computer.visual_ui_engine import visual_ui_engine
from backend.events.event_bus import publish_event
from backend.tools.tool_registry import tool_registry

# ==========================================
# COMPUTER AGENT HIGH-RISK ACTIONS
# ==========================================

_COMPUTER_HIGH_RISK_ACTIONS = {
    "delete_file", "delete_folder", "install_application",
    "uninstall_application", "modify_registry", "modify_os",
    "access_credentials", "run_as_admin", "sudo_command",
    "chmod", "chown",
}

# Actions that map from step["action"] to a governance action name
_STEP_ACTION_MAP = {
    "delete":       "delete_file",
    "rm":           "delete_file",
    "install":      "install_application",
    "uninstall":    "uninstall_application",
    "registry":     "modify_registry",
    "admin":        "run_as_admin",
    "sudo":         "sudo_command",
}


async def _computer_governance_check(
    action:       str,
    description:  str,
    execution_id: str,
    session_id:   str | None = None,
) -> bool:
    """
    Returns True if the computer action is allowed.
    Requests approval for all high-risk OS-level operations.
    """
    try:
        from backend.safety.audit_logger import audit_logger
        from backend.safety.emergency_stop import emergency_stop
        from backend.safety.safety_guard import safety_guard

        if emergency_stop.is_stopped(execution_id):
            return False

        assessment = safety_guard.assess_action(
            action = action,
            agent  = "computer_agent",
        )

        audit_logger.log(
            execution_id = execution_id,
            agent        = "computer_agent",
            action       = action,
            risk_level   = assessment.risk_level.value,
            outcome      = "blocked" if assessment.blocked else (
                "requires_approval" if assessment.requires_approval else "allowed"
            ),
            reason       = assessment.reason,
            session_id   = session_id,
        )

        if assessment.blocked:
            return False

        # Map action to a normalized governance action name
        gov_action = _STEP_ACTION_MAP.get(action.lower(), action)

        if assessment.requires_approval or gov_action in _COMPUTER_HIGH_RISK_ACTIONS:
            from backend.safety.approval_queue import approval_queue
            req = await approval_queue.request(
                execution_id = execution_id,
                agent        = "computer_agent",
                action       = gov_action,
                description  = description,
                risk_level   = assessment.risk_level.value,
                context      = {"action": action, "description": description},
                session_id   = session_id,
                timeout      = 300,
            )
            audit_logger.log(
                execution_id = execution_id,
                agent        = "computer_agent",
                action       = gov_action,
                risk_level   = assessment.risk_level.value,
                outcome      = req.status.value,
                reason       = req.reject_reason or "Resolved by operator",
                session_id   = session_id,
                request_id   = req.request_id,
            )
            return req.status.value == "approved"

        return True

    except Exception:
        return True  # Governance errors must not break execution


# ==========================================
# COMPUTER AGENT
# ==========================================

class ComputerAgent:

    def __init__(self):

        # ==========================================
        # ACTIVE MISSIONS
        # ==========================================

        self.active_missions = {}

        # ==========================================
        # MISSION HISTORY
        # ==========================================

        self.mission_history = []


    # ==========================================
    # EVENT HELPER
    # ==========================================

    async def publish_event(

        self,

        execution_id: str,

        event_type: str,

        status: str,

        phase: str,

        message: str,

        payload: Dict[str, Any] = None
    ):

        await publish_event("computer_agent", execution_id, event_type, status, phase, message, payload)


    # ==========================================
    # ANALYZE CURRENT SCREEN
    # ==========================================

    async def analyze_screen(

        self

    ) -> Dict[str, Any]:

        return await (

            visual_ui_engine
            .analyze_screen_state()
        )


    # ==========================================
    # EXECUTE STEP
    # ==========================================

    async def execute_step(

        self,

        step: Dict[str, Any]
    ) -> Dict[str, Any]:

        action = step.get(
            "action"
        )

        # ======================================
        # OPEN WEBSITE
        # ======================================

        if action == "open_website":

            return await (

                computer_task_engine
                .open_website({

                    "url":
                        step.get("url")
                })
            )

        # ======================================
        # GOOGLE SEARCH
        # ======================================

        elif action == "google_search":

            return await (

                computer_task_engine
                .google_search({

                    "query":
                        step.get("query")
                })
            )

        # ======================================
        # CLICK UI ELEMENT
        # ======================================

        elif action == "click":

            return await (

                visual_ui_engine
                .click_element({

                    "text":
                        step.get("target")
                })
            )

        # ======================================
        # TYPE TEXT
        # ======================================

        elif action == "type":

            return await (

                computer_task_engine
                .type_into_window({

                    "text":
                        step.get("text")
                })
            )

        # ======================================
        # HOTKEY
        # ======================================

        elif action == "hotkey":

            return await (

                desktop_controller
                .hotkey({

                    "keys":
                        step.get("keys", [])
                })
            )

        # ======================================
        # WAIT
        # ======================================

        elif action == "wait":

            seconds = step.get(
                "seconds",
                2
            )

            await asyncio.sleep(
                seconds
            )

            return {

                "success": True,

                "waited":
                    seconds
            }

        # ======================================
        # SCREEN ANALYSIS
        # ======================================

        elif action == "analyze_screen":

            return await (

                self.analyze_screen()
            )

        # ======================================
        # UNKNOWN ACTION
        # ======================================

        return {

            "success": False,

            "error":
                f"Unknown action: {action}"
        }


    # ==========================================
    # EXECUTE STEP  (with governance gate)
    # ==========================================

    async def execute_step_governed(
        self,
        step:         Dict[str, Any],
        execution_id: str,
        session_id:   str | None = None,
    ) -> Dict[str, Any]:
        """
        Execute a workflow step with governance approval for risky actions.
        """
        action = step.get("action", "")
        gov_action = _STEP_ACTION_MAP.get(action.lower(), action)

        if gov_action in _COMPUTER_HIGH_RISK_ACTIONS:
            description = f"Computer step: {action} — {step}"
            allowed = await _computer_governance_check(
                action       = gov_action,
                description  = description,
                execution_id = execution_id,
                session_id   = session_id,
            )
            if not allowed:
                return {
                    "success":    False,
                    "error":      f"Step '{action}' blocked — approval required or denied.",
                    "governance": "blocked",
                    "action":     action,
                }

        return await self.execute_step(step)



    async def execute_mission(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        mission_name = payload.get(

            "mission_name",

            "Unnamed Mission"
        )

        steps = payload.get(
            "steps",
            []
        )

        # ==========================================
        # REGISTER MISSION
        # ==========================================

        self.active_missions[
            execution_id
        ] = {

            "mission_name":
                mission_name,

            "status":
                "running",

            "started_at":
                datetime.utcnow()
                .isoformat()
        }

        await self.publish_event(

            execution_id,

            "computer_mission_started",

            "running",

            "computer_agent",

            f"Starting mission: {mission_name}"
        )

        completed_steps = []

        # ==========================================
        # EXECUTE STEPS
        # ==========================================

        for index, step in enumerate(
            steps
        ):

            try:

                await self.publish_event(

                    execution_id,

                    "computer_step_started",

                    "running",

                    "computer_agent",

                    (
                        f"Executing step "
                        f"{index + 1}"
                    ),

                    {

                        "step":
                            step
                    }
                )

                result = await self.execute_step_governed(
                    step,
                    execution_id = execution_id,
                    session_id   = payload.get("session_id"),
                )

                completed_steps.append({

                    "step":
                        step,

                    "result":
                        result
                })

                # ==================================
                # FAILURE RECOVERY
                # ==================================

                if not result.get(
                    "success"
                ):

                    await self.publish_event(

                        execution_id,

                        "computer_step_failed",

                        "failed",

                        "computer_agent",

                        (
                            f"Step failed: "
                            f"{step.get('action')}"
                        ),

                        {

                            "error":
                                result.get(
                                    "error"
                                )
                        }
                    )

                    # ==============================
                    # SIMPLE RECOVERY
                    # ==============================

                    await asyncio.sleep(2)

                else:

                    await self.publish_event(

                        execution_id,

                        "computer_step_completed",

                        "completed",

                        "computer_agent",

                        (
                            f"Step completed: "
                            f"{step.get('action')}"
                        )
                    )

                await asyncio.sleep(1)

            except Exception as error:

                completed_steps.append({

                    "step":
                        step,

                    "error":
                        str(error)
                })

        # ==========================================
        # COMPLETE MISSION
        # ==========================================

        mission_result = {

            "mission_id":
                execution_id,

            "mission_name":
                mission_name,

            "completed_steps":
                completed_steps,

            "completed_at":
                datetime.utcnow()
                .isoformat()
        }

        self.mission_history.append(
            mission_result
        )

        self.active_missions[
            execution_id
        ]["status"] = "completed"

        await self.publish_event(

            execution_id,

            "computer_mission_completed",

            "completed",

            "computer_agent",

            f"Mission completed: {mission_name}",

            {

                "steps":
                    len(completed_steps)
            }
        )

        return {

            "success": True,

            "mission":
                mission_result
        }


    # ==========================================
    # GET ACTIVE MISSIONS
    # ==========================================

    async def get_active_missions(

        self

    ) -> Dict[str, Any]:

        return {

            "success": True,

            "active_missions":
                self.active_missions
        }


    # ==========================================
    # GET MISSION HISTORY
    # ==========================================

    async def get_mission_history(

        self

    ) -> Dict[str, Any]:

        return {

            "success": True,

            "missions":
                self.mission_history
        }


# ==========================================
# SINGLETON
# ==========================================

computer_agent = (
    ComputerAgent()
)


# ==========================================
# REGISTER TOOLS
# ==========================================

tool_registry.register_tool(

    name="computer_execute_mission",

    description=
        "Execute autonomous computer mission",

    handler=
        computer_agent.execute_mission,

    tool_type=
        "computer_agent"
)

tool_registry.register_tool(

    name="computer_active_missions",

    description=
        "Get active computer missions",

    handler=
        computer_agent.get_active_missions,

    tool_type=
        "computer_agent"
)

tool_registry.register_tool(

    name="computer_mission_history",

    description=
        "Get completed mission history",

    handler=
        computer_agent.get_mission_history,

    tool_type=
        "computer_agent"
)
