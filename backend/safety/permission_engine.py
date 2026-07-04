"""
Permission Engine  (CortexPrime)
==================================
Defines what each agent, user role, and workspace is allowed to do.
Any action not explicitly permitted defaults to DENIED if it is
in a restricted category.

Permission hierarchy
--------------------
ADMIN   — unrestricted (still subject to safety_guard critical blocks)
OPERATOR — can approve actions; can trigger browser + computer agents
USER    — can submit missions; cannot access OS-level actions
READONLY — view-only; cannot trigger any execution
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


# =========================================================
# ROLE DEFINITIONS
# =========================================================

class UserRole(str, Enum):
    ADMIN    = "admin"
    OPERATOR = "operator"
    USER     = "user"
    READONLY = "readonly"


class AgentType(str, Enum):
    ORCHESTRATOR = "orchestrator"
    PLANNER      = "planner"
    RESEARCHER   = "researcher"
    CRITIC       = "critic"
    OPTIMIZER    = "optimizer"
    BROWSER      = "browser_agent"
    COMPUTER     = "computer_agent"
    MEMORY       = "memory"
    VOICE        = "voice"


# =========================================================
# PERMISSION SETS
# =========================================================

# Actions an agent is allowed to perform without any approval gate
_AGENT_ALLOWED: Dict[AgentType, Set[str]] = {
    AgentType.ORCHESTRATOR: {
        "plan_mission", "coordinate_agents", "stream_response",
        "store_memory", "emit_event",
    },
    AgentType.PLANNER: {
        "decompose_objective", "create_plan", "emit_event",
    },
    AgentType.RESEARCHER: {
        "retrieve_memory", "semantic_search", "emit_event",
    },
    AgentType.CRITIC: {
        "validate_plan", "score_confidence", "emit_event",
    },
    AgentType.OPTIMIZER: {
        "optimize_plan", "emit_event",
    },
    AgentType.BROWSER: {
        "navigate", "open_page", "search_web", "extract_content",
        "extract_links", "take_screenshot",
    },
    AgentType.COMPUTER: {
        "analyze_screen", "wait", "take_screenshot",
    },
    AgentType.MEMORY: {
        "store_episodic", "store_semantic", "retrieve_memory",
        "reflect", "emit_event",
    },
    AgentType.VOICE: {
        "speak", "listen", "transcribe",
    },
}

# Actions that always require human approval, regardless of role
_ALWAYS_REQUIRES_APPROVAL: Set[str] = {
    # Browser
    "form_submit", "login", "authenticate", "purchase", "checkout",
    "enter_credentials", "fill_password", "enter_credit_card",
    # Computer
    "delete_file", "delete_folder", "install_application", "uninstall_application",
    "modify_registry", "modify_os", "access_credentials",
    "run_as_admin", "sudo_command", "chmod", "chown",
    # Data
    "drop_database", "truncate_table", "delete_records",
    # Network
    "send_external_request_with_credentials", "expose_port",
}

# User role → set of allowed action categories
_ROLE_PERMISSIONS: Dict[UserRole, Set[str]] = {
    UserRole.ADMIN: {
        "all",
    },
    UserRole.OPERATOR: {
        "mission_execute", "browser_control", "computer_control",
        "approve_action", "reject_action", "emergency_stop",
        "view_queue", "view_audit",
    },
    UserRole.USER: {
        "mission_execute", "view_queue", "view_audit",
    },
    UserRole.READONLY: {
        "view_queue", "view_audit",
    },
}


# =========================================================
# PERMISSION CHECK RESULT
# =========================================================

@dataclass
class PermissionResult:
    allowed:  bool
    reason:   str
    role:     str = ""
    agent:    str = ""
    action:   str = ""


# =========================================================
# PERMISSION ENGINE
# =========================================================

class PermissionEngine:
    """
    Central permission authority for CortexPrime.

    All agent action checks flow through ``check_agent_action``.
    Human action checks flow through ``check_user_action``.
    """

    # ----------------------------------------------------------
    # AGENT PERMISSION CHECK
    # ----------------------------------------------------------

    def check_agent_action(
        self,
        agent:  str,
        action: str,
    ) -> PermissionResult:
        """
        Returns PermissionResult indicating whether an agent may perform
        the action without an additional approval gate.
        """
        # Always-requires-approval set takes absolute priority
        if action in _ALWAYS_REQUIRES_APPROVAL:
            return PermissionResult(
                allowed = False,
                reason  = f"Action '{action}' always requires human approval.",
                agent   = agent,
                action  = action,
            )

        # Map string to AgentType; default to treating as orchestrator
        try:
            agent_enum = AgentType(agent)
        except ValueError:
            agent_enum = AgentType.ORCHESTRATOR

        allowed_set = _AGENT_ALLOWED.get(agent_enum, set())
        if action in allowed_set:
            return PermissionResult(
                allowed = True,
                reason  = f"Agent '{agent}' is permitted to '{action}'.",
                agent   = agent,
                action  = action,
            )

        # Unknown action — default DENY
        return PermissionResult(
            allowed = False,
            reason  = f"Action '{action}' is not in the permitted set for agent '{agent}'.",
            agent   = agent,
            action  = action,
        )

    # ----------------------------------------------------------
    # USER PERMISSION CHECK
    # ----------------------------------------------------------

    def check_user_action(
        self,
        user_role: str,
        action:    str,
    ) -> PermissionResult:
        """Check whether a user with the given role may trigger an action."""
        try:
            role_enum = UserRole(user_role)
        except ValueError:
            role_enum = UserRole.USER

        permissions = _ROLE_PERMISSIONS.get(role_enum, set())

        if "all" in permissions:
            return PermissionResult(
                allowed = True,
                reason  = f"Role '{user_role}' has unrestricted access.",
                role    = user_role,
                action  = action,
            )

        if action in permissions:
            return PermissionResult(
                allowed = True,
                reason  = f"Role '{user_role}' is permitted to '{action}'.",
                role    = user_role,
                action  = action,
            )

        return PermissionResult(
            allowed = False,
            reason  = f"Role '{user_role}' does not have permission for '{action}'.",
            role    = user_role,
            action  = action,
        )

    # ----------------------------------------------------------
    # WORKSPACE PERMISSION CHECK
    # ----------------------------------------------------------

    def check_workspace_action(
        self,
        workspace_id: str,
        action:       str,
    ) -> PermissionResult:
        """
        Workspace-scoped permission gate.
        Currently all workspaces allow standard actions.
        Future: load per-workspace policy from database.
        """
        blocked_in_workspace = {
            "delete_all_workspace_files",
            "export_workspace_data",
        }
        if action in blocked_in_workspace:
            return PermissionResult(
                allowed = False,
                reason  = f"Action '{action}' is blocked in workspace scope.",
                action  = action,
            )
        return PermissionResult(
            allowed = True,
            reason  = "Workspace scope: action allowed.",
            action  = action,
        )

    # ----------------------------------------------------------
    # CONVENIENCE: DOES THIS ACTION REQUIRE APPROVAL?
    # ----------------------------------------------------------

    def requires_approval(self, action: str) -> bool:
        return action in _ALWAYS_REQUIRES_APPROVAL


# =========================================================
# SINGLETON
# =========================================================

permission_engine = PermissionEngine()
