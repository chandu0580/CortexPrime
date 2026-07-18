"""
Enterprise Mission Templates — blueprint definitions for 7 common enterprise workflows.

Each template defines:
  - A connector chain (ordered operations across multiple connectors)
  - Recovery rules (retry, rollback, alternatives, escalation)
  - Approval gates (where human intervention is required)
  - Verification rules (how to confirm each step succeeded)

Templates are pure data — no executable code. The EnterpriseMissionOrchestrator
interprets them at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ConnectorStep:
    """A single operation on an enterprise connector in the chain."""
    connector_type: str
    operation: str
    params: Dict[str, Any]
    description: str = ""
    """Human-readable label for this step (shown in UI / logs)."""

    output_mapping: Dict[str, str] = field(default_factory=dict)
    """Map this step's output keys → input param keys on the next step.
       E.g. {"issue_number": "issue_id"} means the 'issue_number' field
       from this step's result becomes the 'issue_id' param of the next step."""


@dataclass
class ApprovalGate:
    """A point in the workflow where human approval is required."""
    after_step: int
    """Index in the connector chain after which approval is needed."""
    reason: str = ""
    timeout_seconds: int = 300
    required_role: str = "admin"


@dataclass
class RecoveryRule:
    """Recovery strategy for a step that fails."""
    max_retries: int = 2
    """Number of automatic retries before falling through."""
    alternative_connector: Optional[str] = None
    """Fallback connector type if the primary is unavailable."""
    alternative_operation: Optional[str] = None
    """Fallback operation on the alternative connector."""
    rollback_steps: List[int] = field(default_factory=list)
    """Indices of earlier steps to undo on catastrophic failure."""
    escalate_after_retries: bool = True
    """Whether to escalate to human approval after retries exhausted."""


@dataclass
class MissionTemplate:
    """Blueprint for an enterprise mission."""
    id: str
    name: str
    description: str
    category: str
    icon: str = "Zap"

    pipeline_stages: List[str] = field(default_factory=lambda: [
        "INIT", "PLANNING", "REASONING", "VALIDATING", "GENERATING", "MEMORY_UPDATE",
    ])
    """Stages to run through the cognition pipeline."""

    connector_chain: List[ConnectorStep] = field(default_factory=list)
    """Ordered list of connector operations to execute."""

    approval_gates: List[ApprovalGate] = field(default_factory=list)
    """Points at which human approval is required."""

    recovery: RecoveryRule = field(default_factory=RecoveryRule)
    """Default recovery strategy for connector steps."""

    verify_each_step: bool = True
    """Whether to run verification after each connector step."""

    default_params: Dict[str, Any] = field(default_factory=dict)
    """Default parameter values for the template."""

    required_params: List[str] = field(default_factory=list)
    """Parameter names that must be provided at launch time."""


# ===================================================================
# 7 Enterprise Templates
# ===================================================================

SOFTWARE_RELEASE_TEMPLATE = MissionTemplate(
    id="software_release",
    name="Software Release",
    description="Automated software release pipeline — create release branch, build, deploy, notify, document.",
    category="engineering",
    icon="GitBranch",
    required_params=["version", "repository", "release_notes"],
    default_params={
        "branch_prefix": "release/",
        "notify_channel": "#releases",
    },
    connector_chain=[
        ConnectorStep(
            connector_type="github",
            operation="create_branch",
            params={"repository": "{{repository}}", "branch": "release/{{version}}", "source": "main"},
            description="Create release branch from main",
            output_mapping={"branch": "branch_name"},
        ),
        ConnectorStep(
            connector_type="azure_devops",
            operation="create_release",
            params={"definition_id": "{{definition_id}}", "branch": "release/{{version}}"},
            description="Trigger build and release pipeline",
            output_mapping={"release_id": "release_id"},
        ),
        ConnectorStep(
            connector_type="slack",
            operation="send_message",
            params={"channel": "{{notify_channel}}", "text": "Release {{version}} is now building. Release ID: {{release_id}}"},
            description="Notify team about the release",
        ),
        ConnectorStep(
            connector_type="confluence",
            operation="create_page",
            params={"space": "{{space_key}}", "title": "Release Notes {{version}}", "body": "{{release_notes}}"},
            description="Publish release notes",
        ),
    ],
    approval_gates=[
        ApprovalGate(after_step=0, reason="Release branch created — approve to proceed with build", timeout_seconds=600),
        ApprovalGate(after_step=2, reason="Build complete — approve to publish documentation", timeout_seconds=300),
    ],
    recovery=RecoveryRule(
        max_retries=2,
        alternative_connector="github",
        alternative_operation="create_tag",
        rollback_steps=[0],
        escalate_after_retries=True,
    ),
)


INCIDENT_RESPONSE_TEMPLATE = MissionTemplate(
    id="incident_response",
    name="Incident Response",
    description="Automated incident response — create ticket, notify responders, post update, document RCA.",
    category="operations",
    icon="AlertTriangle",
    required_params=["incident_title", "severity", "description"],
    default_params={
        "priority": "P1",
    },
    connector_chain=[
        ConnectorStep(
            connector_type="servicenow",
            operation="create_incident",
            params={"short_description": "{{incident_title}}", "description": "{{description}}", "urgency": "{{severity}}"},
            description="Create incident in ServiceNow",
            output_mapping={"incident_number": "incident_id"},
        ),
        ConnectorStep(
            connector_type="slack",
            operation="send_message",
            params={"channel": "#incidents", "text": "🚨 *Incident {{incident_id}}*: {{incident_title}}\nSeverity: {{severity}}\n{{description}}"},
            description="Alert incident response channel",
        ),
        ConnectorStep(
            connector_type="jira",
            operation="create_issue",
            params={"project": "{{jira_project}}", "summary": "[Incident {{incident_id}}] {{incident_title}}", "priority": "{{severity}}"},
            description="Create tracking issue in Jira",
            output_mapping={"issue_key": "issue_key"},
        ),
        ConnectorStep(
            connector_type="teams",
            operation="send_message",
            params={"channel": "incident-response", "message": "Incident {{incident_id}} tracked as {{issue_key}}"},
            description="Notify Microsoft Teams channel",
        ),
        ConnectorStep(
            connector_type="confluence",
            operation="create_page",
            params={"space": "{{space_key}}", "title": "RCA: {{incident_title}} ({{incident_id}})", "body": "# Root Cause Analysis\n\n## Summary\n{{description}}\n\n## Timeline\n\n## Resolution\n\n## Action Items\n"},
            description="Create RCA document template",
        ),
    ],
    approval_gates=[
        ApprovalGate(after_step=0, reason="Incident created — approve to notify responders", timeout_seconds=120),
    ],
    recovery=RecoveryRule(max_retries=3, escalate_after_retries=True),
)


BUG_TRIAGE_TEMPLATE = MissionTemplate(
    id="bug_triage",
    name="Bug Triage",
    description="Triage a reported bug — classify, create issue, assign, notify, document workaround.",
    category="engineering",
    icon="Bug",
    required_params=["bug_title", "description", "reporter"],
    connector_chain=[
        ConnectorStep(
            connector_type="github",
            operation="create_issue",
            params={"repository": "{{repository}}", "title": "{{bug_title}}", "body": "{{description}}", "labels": ["bug"]},
            description="Create GitHub issue",
            output_mapping={"issue_number": "issue_number"},
        ),
        ConnectorStep(
            connector_type="jira",
            operation="create_issue",
            params={"project": "{{jira_project}}", "summary": "[BUG #{{issue_number}}] {{bug_title}}", "issuetype": "Bug", "priority": "{{priority}}"},
            description="Create Jira bug ticket",
            output_mapping={"issue_key": "issue_key"},
        ),
        ConnectorStep(
            connector_type="slack",
            operation="send_message",
            params={"channel": "#bug-triage", "text": "🐛 Bug reported by {{reporter}}: *{{bug_title}}*\nGitHub: #{{issue_number}} | Jira: {{issue_key}}\n{{description}}"},
            description="Notify triage channel",
        ),
        ConnectorStep(
            connector_type="confluence",
            operation="create_page",
            params={"space": "{{space_key}}", "title": "Bug Report: {{bug_title}}", "body": "## Bug Report\n**Reporter:** {{reporter}}\n**Issue:** {{issue_key}}\n\n{{description}}\n\n## Workaround\n\n## Resolution\n"},
            description="Create bug report page",
        ),
    ],
    recovery=RecoveryRule(max_retries=2, escalate_after_retries=True),
)


INFRASTRUCTURE_CHANGE_TEMPLATE = MissionTemplate(
    id="infrastructure_change",
    name="Infrastructure Change",
    description="Execute an infrastructure change — create ticket, approve, apply, verify, document.",
    category="operations",
    icon="Server",
    required_params=["change_title", "description", "change_type"],
    connector_chain=[
        ConnectorStep(
            connector_type="servicenow",
            operation="create_change_request",
            params={"short_description": "{{change_title}}", "description": "{{description}}", "type": "{{change_type}}"},
            description="Create change request in ServiceNow",
            output_mapping={"change_number": "change_id"},
        ),
        ConnectorStep(
            connector_type="jira",
            operation="create_issue",
            params={"project": "{{jira_project}}", "summary": "[Change {{change_id}}] {{change_title}}", "issuetype": "Task"},
            description="Create tracking issue",
            output_mapping={"issue_key": "issue_key"},
        ),
        ConnectorStep(
            connector_type="slack",
            operation="send_message",
            params={"channel": "#infra-changes", "text": "🔧 Infrastructure change {{change_id}}: *{{change_title}}*\nType: {{change_type}}\nTracked as {{issue_key}}"},
            description="Notify infrastructure team",
        ),
        ConnectorStep(
            connector_type="teams",
            operation="send_message",
            params={"channel": "infrastructure", "message": "Change {{change_id}} ({{change_title}}) — {{issue_key}} — awaiting approval"},
            description="Post to Teams infrastructure channel",
        ),
        ConnectorStep(
            connector_type="confluence",
            operation="create_page",
            params={"space": "{{space_key}}", "title": "Change Record: {{change_id}} — {{change_title}}", "body": "## Infrastructure Change\n**ID:** {{change_id}}\n**Title:** {{change_title}}\n**Type:** {{change_type}}\n\n{{description}}\n\n## Implementation Plan\n\n## Rollback Plan\n\n## Verification\n"},
            description="Document change in Confluence",
        ),
    ],
    approval_gates=[
        ApprovalGate(after_step=1, reason="Change request created — approve to proceed with execution", timeout_seconds=900),
    ],
    recovery=RecoveryRule(max_retries=1, rollback_steps=[0, 1], escalate_after_retries=True),
)


EMPLOYEE_ONBOARDING_TEMPLATE = MissionTemplate(
    id="employee_onboarding",
    name="Employee Onboarding",
    description="Onboard a new employee — create accounts, assign tasks, notify teams, document setup.",
    category="hr",
    icon="UserPlus",
    required_params=["employee_name", "employee_email", "department", "start_date"],
    connector_chain=[
        ConnectorStep(
            connector_type="jira",
            operation="create_issue",
            params={"project": "{{jira_project}}", "summary": "Onboard {{employee_name}} ({{department}})", "issuetype": "Task", "description": "New employee onboarding for {{employee_name}} starting {{start_date}}"},
            description="Create onboarding epic",
            output_mapping={"issue_key": "epic_key"},
        ),
        ConnectorStep(
            connector_type="slack",
            operation="send_message",
            params={"channel": "#onboarding", "text": "👋 Welcome {{employee_name}}! Starting {{start_date}} in {{department}}. Tracked as {{epic_key}}"},
            description="Announce new hire",
        ),
        ConnectorStep(
            connector_type="teams",
            operation="send_message",
            params={"channel": "onboarding", "message": "New team member: {{employee_name}} ({{department}}). Onboarding epic: {{epic_key}}"},
            description="Post to Teams onboarding channel",
        ),
        ConnectorStep(
            connector_type="confluence",
            operation="create_page",
            params={"space": "{{space_key}}", "title": "Onboarding: {{employee_name}}", "body": "## Employee Onboarding\n**Name:** {{employee_name}}\n**Email:** {{employee_email}}\n**Department:** {{department}}\n**Start Date:** {{start_date}}\n\n## Checklist\n- [ ] IT account setup\n- [ ] Email distribution lists\n- [ ] Workspace access\n- [ ] Equipment\n- [ ] Orientation\n\n## Notes\n"},
            description="Create onboarding checklist page",
        ),
    ],
    recovery=RecoveryRule(max_retries=2, escalate_after_retries=True),
)


CUSTOMER_ESCALATION_TEMPLATE = MissionTemplate(
    id="customer_escalation",
    name="Customer Escalation",
    description="Handle a customer escalation — create ticket, notify support, post update, document resolution.",
    category="support",
    icon="MessageSquare",
    required_params=["customer_name", "escalation_reason", "severity", "account_id"],
    connector_chain=[
        ConnectorStep(
            connector_type="servicenow",
            operation="create_incident",
            params={"short_description": "Escalation: {{customer_name}}", "description": "{{escalation_reason}}", "urgency": "{{severity}}"},
            description="Create escalation incident",
            output_mapping={"incident_number": "incident_id"},
        ),
        ConnectorStep(
            connector_type="slack",
            operation="send_message",
            params={"channel": "#customer-support", "text": "⚠️ *Customer Escalation* — {{customer_name}} ({{account_id}})\nSeverity: {{severity}}\nIncident: {{incident_id}}\n\n{{escalation_reason}}"},
            description="Alert support channel",
        ),
        ConnectorStep(
            connector_type="jira",
            operation="create_issue",
            params={"project": "{{jira_project}}", "summary": "[ESC {{incident_id}}] {{customer_name}} — {{escalation_reason}}", "priority": "{{severity}}"},
            description="Create escalation issue",
            output_mapping={"issue_key": "issue_key"},
        ),
        ConnectorStep(
            connector_type="teams",
            operation="send_message",
            params={"channel": "customer-escalations", "message": "Escalation {{incident_id}} for {{customer_name}} — tracked as {{issue_key}}"},
            description="Notify Teams escalation channel",
        ),
    ],
    approval_gates=[
        ApprovalGate(after_step=0, reason="Escalation created — approve to proceed with response", timeout_seconds=180),
    ],
    recovery=RecoveryRule(max_retries=2, escalate_after_retries=True),
)


KNOWLEDGE_PUBLISHING_TEMPLATE = MissionTemplate(
    id="knowledge_publishing",
    name="Knowledge Publishing",
    description="Publish knowledge content — create document, review, approve, publish, notify.",
    category="content",
    icon="FileText",
    required_params=["title", "content", "author", "space_key"],
    connector_chain=[
        ConnectorStep(
            connector_type="confluence",
            operation="create_page",
            params={"space": "{{space_key}}", "title": "{{title}}", "body": "{{content}}"},
            description="Create draft page in Confluence",
            output_mapping={"page_id": "page_id"},
        ),
        ConnectorStep(
            connector_type="slack",
            operation="send_message",
            params={"channel": "#documentation", "text": "📄 *New documentation: {{title}}*\nAuthor: {{author}}\nReview at: https://{{domain}}.atlassian.net/wiki/spaces/{{space_key}}/pages/{{page_id}}"},
            description="Request review in documentation channel",
        ),
        ConnectorStep(
            connector_type="teams",
            operation="send_message",
            params={"channel": "documentation", "message": "New doc: {{title}} by {{author}} — please review: Confluence page {{page_id}}"},
            description="Post to Teams documentation channel",
        ),
    ],
    approval_gates=[
        ApprovalGate(after_step=1, reason="Documentation created — approve to publish and notify", timeout_seconds=604800),
    ],
    recovery=RecoveryRule(max_retries=2, escalate_after_retries=True),
)


# ===================================================================
# Registry
# ===================================================================

_ALL_TEMPLATES: List[MissionTemplate] = [
    SOFTWARE_RELEASE_TEMPLATE,
    INCIDENT_RESPONSE_TEMPLATE,
    BUG_TRIAGE_TEMPLATE,
    INFRASTRUCTURE_CHANGE_TEMPLATE,
    EMPLOYEE_ONBOARDING_TEMPLATE,
    CUSTOMER_ESCALATION_TEMPLATE,
    KNOWLEDGE_PUBLISHING_TEMPLATE,
]

_TEMPLATE_MAP: Dict[str, MissionTemplate] = {t.id: t for t in _ALL_TEMPLATES}


def list_templates() -> List[MissionTemplate]:
    return list(_ALL_TEMPLATES)


def get_template(template_id: str) -> Optional[MissionTemplate]:
    return _TEMPLATE_MAP.get(template_id)


def template_to_dict(t: MissionTemplate) -> Dict[str, Any]:
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "category": t.category,
        "icon": t.icon,
        "requiredParams": t.required_params,
        "defaultParams": t.default_params,
        "pipelineStages": t.pipeline_stages,
        "connectorChain": [
            {
                "connectorType": s.connector_type,
                "operation": s.operation,
                "params": s.params,
                "description": s.description,
                "outputMapping": s.output_mapping,
            }
            for s in t.connector_chain
        ],
        "approvalGates": [
            {
                "afterStep": g.after_step,
                "reason": g.reason,
                "timeoutSeconds": g.timeout_seconds,
                "requiredRole": g.required_role,
            }
            for g in t.approval_gates
        ],
        "recovery": {
            "maxRetries": t.recovery.max_retries,
            "alternativeConnector": t.recovery.alternative_connector,
            "alternativeOperation": t.recovery.alternative_operation,
            "rollbackSteps": t.recovery.rollback_steps,
            "escalateAfterRetries": t.recovery.escalate_after_retries,
        },
        "verifyEachStep": t.verify_each_step,
    }
