from __future__ import annotations

from backend.mission_library.models import (
    AuditLevel,
    ConnectorType,
    ExecutionStage,
    FailureRecovery,
    GovernanceLevel,
    MissionCategory,
    MissionDefinition,
    MissionMetadata,
    RetryPolicy,
    SuccessCriterion,
    WorkerType,
)

# ==============================================================================
# 1. SOFTWARE RELEASE
# ==============================================================================

SOFTWARE_RELEASE = MissionDefinition(
    metadata=MissionMetadata(
        id="enterprise.software_release",
        name="Software Release",
        version="1.0.0",
        description="Plan, coordinate, and document a production software release across environments.",
        category=MissionCategory.SOFTWARE_RELEASE,
        tags=["release", "deployment", "ci-cd", "rollback"],
    ),
    objective_template=(
        "Plan and document a production software release for {project_name}. "
        "Version {version} is being deployed to {environment}. "
        "Key changes include: {changes}. "
        "Rollback plan: {rollback_plan}. "
        "Stakeholders to notify: {stakeholders}. "
        "Provide a detailed release plan covering pre-deployment checks, "
        "deployment steps, post-deployment validation, monitoring, and rollback procedures."
    ),
    objectives=[
        "Analyze the release scope and changes",
        "Verify pre-deployment checks and dependencies",
        "Document deployment steps with rollback at each stage",
        "Plan canary/blue-green deployment strategy",
        "Define post-deployment validation criteria",
        "Document monitoring and alerting thresholds",
        "Generate release summary for stakeholders",
    ],
    required_workers=[WorkerType.BROWSER],
    required_connectors=[ConnectorType.RABBITMQ, ConnectorType.REDIS, ConnectorType.NEO4J],
    required_approvals=GovernanceLevel.HIGH,
    execution_stages=[
        ExecutionStage.INIT,
        ExecutionStage.PLANNING,
        ExecutionStage.RESEARCHING,
        ExecutionStage.VALIDATING,
        ExecutionStage.GENERATING,
        ExecutionStage.MEMORY_UPDATE,
        ExecutionStage.COMPLETED,
    ],
    success_criteria=[
        SuccessCriterion(description="Release plan includes rollback at every stage"),
        SuccessCriterion(description="Pre-deployment checklist is complete"),
        SuccessCriterion(description="Post-deployment validation criteria defined"),
        SuccessCriterion(description="Stakeholder notification plan documented"),
        SuccessCriterion(description="Monitoring thresholds specified"),
    ],
    failure_recovery=FailureRecovery(
        description="Rollback all deployment steps. Notify release engineer.",
        rollback_action="Revert to last known good version across all environments.",
    ),
    retry_policy=RetryPolicy(max_retries=2, backoff_seconds=5.0),
    audit_requirements=AuditLevel.DETAILED,
    needs_browser=True,
)

# ==============================================================================
# 2. INCIDENT RESPONSE
# ==============================================================================

INCIDENT_RESPONSE = MissionDefinition(
    metadata=MissionMetadata(
        id="enterprise.incident_response",
        name="Incident Response",
        version="1.0.0",
        description="Respond to a production incident with triage, root cause analysis, and remediation plan.",
        category=MissionCategory.INCIDENT_RESPONSE,
        tags=["incident", "sre", "observability", "root-cause", "remediation"],
    ),
    objective_template=(
        "Respond to a production incident in {system_name}. "
        "Severity: {severity}. "
        "Symptoms reported: {symptoms}. "
        "Affected services: {affected_services}. "
        "Current impact: {impact}. "
        "Provide a structured incident response including: "
        "immediate triage steps, root cause analysis approach, "
        "mitigation strategy, remediation plan, and post-incident review checklist."
    ),
    objectives=[
        "Triage and assess incident severity and impact",
        "Analyze symptoms and affected services",
        "Identify potential root causes",
        "Document immediate mitigation steps",
        "Plan remediation with validation",
        "Outline post-incident review process",
        "Document lessons learned",
    ],
    required_workers=[WorkerType.BROWSER],
    required_connectors=[ConnectorType.RABBITMQ, ConnectorType.REDIS, ConnectorType.NEO4J],
    required_approvals=GovernanceLevel.HIGH,
    success_criteria=[
        SuccessCriterion(description="Root cause hypothesis documented"),
        SuccessCriterion(description="Immediate mitigation steps defined"),
        SuccessCriterion(description="Remediation plan with validation steps"),
        SuccessCriterion(description="Post-incident review checklist"),
        SuccessCriterion(description="Lessons learned captured"),
    ],
    failure_recovery=FailureRecovery(
        description="Escalate to on-call SRE team leader. Log all findings.",
        rollback_action="Apply the proposed mitigation steps immediately.",
    ),
    retry_policy=RetryPolicy(max_retries=1, backoff_seconds=3.0),
    audit_requirements=AuditLevel.DETAILED,
    needs_browser=True,
)

# ==============================================================================
# 3. EXECUTIVE RESEARCH
# ==============================================================================

EXECUTIVE_RESEARCH = MissionDefinition(
    metadata=MissionMetadata(
        id="enterprise.executive_research",
        name="Executive Research",
        version="1.0.0",
        description="Conduct deep research on a strategic topic and produce an executive briefing.",
        category=MissionCategory.EXECUTIVE_RESEARCH,
        tags=["research", "executive", "strategy", "briefing", "analysis"],
    ),
    objective_template=(
        "Conduct comprehensive research on {topic} for executive leadership. "
        "Context: {context}. "
        "Key questions to address: {questions}. "
        "Focus areas: {focus_areas}. "
        "Produce an executive briefing covering: market landscape, competitive analysis, "
        "key trends, strategic recommendations, risk assessment, and action items."
    ),
    objectives=[
        "Research the topic comprehensively",
        "Analyze competitive landscape and market trends",
        "Identify strategic opportunities and risks",
        "Formulate actionable recommendations",
        "Generate executive summary",
        "Document sources and methodology",
    ],
    required_workers=[WorkerType.BROWSER],
    required_connectors=[ConnectorType.REDIS, ConnectorType.NEO4J],
    required_approvals=GovernanceLevel.LOW,
    success_criteria=[
        SuccessCriterion(description="Research covers all focus areas"),
        SuccessCriterion(description="Competitive analysis included"),
        SuccessCriterion(description="Strategic recommendations are actionable"),
        SuccessCriterion(description="Risk assessment documented"),
        SuccessCriterion(description="Sources cited"),
    ],
    failure_recovery=FailureRecovery(
        description="Return partial research with gaps noted. Flag for human review.",
    ),
    retry_policy=RetryPolicy(max_retries=2, backoff_seconds=3.0),
    audit_requirements=AuditLevel.STANDARD,
    needs_browser=True,
)

# ==============================================================================
# 4. COMPLIANCE AUDIT
# ==============================================================================

COMPLIANCE_AUDIT = MissionDefinition(
    metadata=MissionMetadata(
        id="enterprise.compliance_audit",
        name="Compliance Audit",
        version="1.0.0",
        description="Perform a structured compliance audit against regulatory frameworks.",
        category=MissionCategory.COMPLIANCE_AUDIT,
        tags=["compliance", "audit", "regulatory", "security", "governance"],
    ),
    objective_template=(
        "Perform a compliance audit for {organization} against {framework}. "
        "Scope: {scope}. "
        "Controls to assess: {controls}. "
        "Evidence available: {evidence}. "
        "Produce a structured audit report covering: control assessment findings, "
        "gaps and risks, remediation recommendations, compliance score, "
        "and evidence traceability matrix."
    ),
    objectives=[
        "Review compliance requirements and control framework",
        "Assess each control against available evidence",
        "Identify compliance gaps and risks",
        "Score compliance maturity",
        "Document remediation recommendations",
        "Generate audit report with evidence traceability",
    ],
    required_workers=[WorkerType.BROWSER],
    required_connectors=[ConnectorType.REDIS, ConnectorType.NEO4J],
    required_approvals=GovernanceLevel.HIGH,
    success_criteria=[
        SuccessCriterion(description="All controls assessed"),
        SuccessCriterion(description="Compliance gaps identified"),
        SuccessCriterion(description="Remediation plan documented"),
        SuccessCriterion(description="Evidence traceability matrix complete"),
        SuccessCriterion(description="Compliance score calculated"),
    ],
    failure_recovery=FailureRecovery(
        description="Log partial audit results. Flag for compliance officer review.",
        rollback_action="Archive all audit findings for regulatory review.",
    ),
    retry_policy=RetryPolicy(max_retries=2, backoff_seconds=5.0),
    audit_requirements=AuditLevel.FULL,
    needs_browser=True,
)

# ==============================================================================
# 5. CHANGE MANAGEMENT
# ==============================================================================

CHANGE_MANAGEMENT = MissionDefinition(
    metadata=MissionMetadata(
        id="enterprise.change_management",
        name="Change Management",
        version="1.0.0",
        description="Plan and document an organizational or technical change with impact assessment.",
        category=MissionCategory.CHANGE_MANAGEMENT,
        tags=["change", "itil", "impact", "stakeholder", "governance"],
    ),
    objective_template=(
        "Plan and document a change for {organization}. "
        "Change description: {change_description}. "
        "Affected systems: {affected_systems}. "
        "Stakeholders: {stakeholders}. "
        "Risk level: {risk_level}. "
        "Change window: {change_window}. "
        "Produce a change management plan including: change summary, "
        "impact assessment, implementation steps, rollback plan, "
        "testing criteria, stakeholder communications, and CAB submission."
    ),
    objectives=[
        "Assess change impact across systems and stakeholders",
        "Document implementation plan with timelines",
        "Define testing and validation criteria",
        "Create rollback procedures for each phase",
        "Plan stakeholder communications",
        "Prepare CAB submission materials",
    ],
    required_workers=[WorkerType.BROWSER],
    required_connectors=[ConnectorType.RABBITMQ, ConnectorType.REDIS, ConnectorType.NEO4J],
    required_approvals=GovernanceLevel.MEDIUM,
    success_criteria=[
        SuccessCriterion(description="Impact assessment covers all affected systems"),
        SuccessCriterion(description="Implementation plan with timelines"),
        SuccessCriterion(description="Rollback procedures defined"),
        SuccessCriterion(description="Testing criteria documented"),
        SuccessCriterion(description="CAB submission materials prepared"),
    ],
    failure_recovery=FailureRecovery(
        description="Document partial plan. Escalate to change manager.",
        rollback_action="Revert to current state documentation.",
    ),
    retry_policy=RetryPolicy(max_retries=2, backoff_seconds=3.0),
    audit_requirements=AuditLevel.DETAILED,
    needs_browser=True,
)

# ==============================================================================
# 6. INFRASTRUCTURE DEPLOYMENT
# ==============================================================================

INFRASTRUCTURE_DEPLOYMENT = MissionDefinition(
    metadata=MissionMetadata(
        id="enterprise.infrastructure_deployment",
        name="Infrastructure Deployment",
        version="1.0.0",
        description="Design and document an infrastructure deployment with architecture validation.",
        category=MissionCategory.INFRASTRUCTURE_DEPLOYMENT,
        tags=["infrastructure", "cloud", "terraform", "kubernetes", "networking"],
    ),
    objective_template=(
        "Design and document an infrastructure deployment for {project_name}. "
        "Cloud provider: {cloud_provider}. "
        "Architecture: {architecture}. "
        "Components to deploy: {components}. "
        "Networking requirements: {networking}. "
        "Compliance requirements: {compliance}. "
        "Provide a comprehensive deployment plan covering: architecture design, "
        "resource provisioning order, networking setup, security groups, "
        "monitoring configuration, backup strategy, and validation tests."
    ),
    objectives=[
        "Design infrastructure architecture",
        "Plan resource provisioning order and dependencies",
        "Define networking and security configurations",
        "Document monitoring and alerting setup",
        "Plan backup and disaster recovery strategy",
        "Define validation and smoke tests",
        "Generate deployment runbook",
    ],
    required_workers=[WorkerType.BROWSER],
    required_connectors=[ConnectorType.RABBITMQ, ConnectorType.REDIS, ConnectorType.NEO4J],
    required_approvals=GovernanceLevel.HIGH,
    success_criteria=[
        SuccessCriterion(description="Architecture diagram documented"),
        SuccessCriterion(description="Resource provisioning order defined"),
        SuccessCriterion(description="Security groups and networking configured"),
        SuccessCriterion(description="Monitoring and alerting plan"),
        SuccessCriterion(description="Backup and DR strategy defined"),
        SuccessCriterion(description="Deployment runbook complete"),
    ],
    failure_recovery=FailureRecovery(
        description="Halt deployment. Notify infrastructure team lead.",
        rollback_action="Preserve current infrastructure state. Document rollback steps.",
    ),
    retry_policy=RetryPolicy(max_retries=2, backoff_seconds=5.0),
    audit_requirements=AuditLevel.DETAILED,
    needs_browser=True,
)

# ==============================================================================
# 7. SECURITY INVESTIGATION
# ==============================================================================

SECURITY_INVESTIGATION = MissionDefinition(
    metadata=MissionMetadata(
        id="enterprise.security_investigation",
        name="Security Investigation",
        version="1.0.0",
        description="Investigate a security alert with threat analysis and remediation recommendations.",
        category=MissionCategory.SECURITY_INVESTIGATION,
        tags=["security", "investigation", "threat", "incident", "forensics"],
    ),
    objective_template=(
        "Investigate a security alert for {organization}. "
        "Alert type: {alert_type}. "
        "Severity: {severity}. "
        "Indicators of compromise: {iocs}. "
        "Affected assets: {affected_assets}. "
        "Timeframe: {timeframe}. "
        "Produce a security investigation report covering: alert analysis, "
        "threat actor profiling, attack chain reconstruction, "
        "affected systems assessment, containment recommendations, "
        "eradication steps, and prevention measures."
    ),
    objectives=[
        "Analyze the security alert and indicators of compromise",
        "Reconstruct the attack chain and timeline",
        "Profile the threat actor and TTPs",
        "Assess affected systems and data exposure",
        "Document containment and eradication steps",
        "Recommend prevention and detection improvements",
    ],
    required_workers=[WorkerType.BROWSER],
    required_connectors=[ConnectorType.REDIS, ConnectorType.NEO4J],
    required_approvals=GovernanceLevel.CRITICAL,
    success_criteria=[
        SuccessCriterion(description="Attack chain reconstructed"),
        SuccessCriterion(description="Affected systems identified"),
        SuccessCriterion(description="Containment steps documented"),
        SuccessCriterion(description="Eradication plan defined"),
        SuccessCriterion(description="Prevention recommendations provided"),
    ],
    failure_recovery=FailureRecovery(
        description="Escalate to security team lead immediately. Containment is priority.",
        rollback_action="Isolate affected systems. Preserve forensic evidence.",
    ),
    retry_policy=RetryPolicy(max_retries=1, backoff_seconds=2.0),
    audit_requirements=AuditLevel.FULL,
    needs_browser=True,
)

# ==============================================================================
# 8. KNOWLEDGE DISCOVERY
# ==============================================================================

KNOWLEDGE_DISCOVERY = MissionDefinition(
    metadata=MissionMetadata(
        id="enterprise.knowledge_discovery",
        name="Knowledge Discovery",
        version="1.0.0",
        description="Discover, synthesize, and organize knowledge on a domain from multiple sources.",
        category=MissionCategory.KNOWLEDGE_DISCOVERY,
        tags=["knowledge", "research", "synthesis", "documentation", "learning"],
    ),
    objective_template=(
        "Discover and synthesize knowledge about {topic}. "
        "Context: {context}. "
        "Sources to explore: {sources}. "
        "Key areas to cover: {focus_areas}. "
        "Produce a comprehensive knowledge document covering: domain overview, "
        "key concepts and definitions, architectural patterns, "
        "best practices, tooling ecosystem, common pitfalls, "
        "and a structured learning path."
    ),
    objectives=[
        "Research the topic from multiple sources",
        "Identify key concepts, patterns, and terminology",
        "Document architectural approaches and best practices",
        "Map the tooling and technology ecosystem",
        "Identify common pitfalls and anti-patterns",
        "Create a structured learning path",
    ],
    required_workers=[WorkerType.BROWSER],
    required_connectors=[ConnectorType.REDIS, ConnectorType.NEO4J],
    required_approvals=GovernanceLevel.LOW,
    success_criteria=[
        SuccessCriterion(description="All focus areas covered"),
        SuccessCriterion(description="Key concepts defined and explained"),
        SuccessCriterion(description="Best practices documented"),
        SuccessCriterion(description="Learning path structured"),
        SuccessCriterion(description="Sources cited"),
    ],
    failure_recovery=FailureRecovery(
        description="Return partial knowledge document with gaps flagged.",
    ),
    retry_policy=RetryPolicy(max_retries=3, backoff_seconds=2.0),
    audit_requirements=AuditLevel.STANDARD,
    needs_browser=True,
)

# ==============================================================================
# 9. CUSTOMER ESCALATION
# ==============================================================================

CUSTOMER_ESCALATION = MissionDefinition(
    metadata=MissionMetadata(
        id="enterprise.customer_escalation",
        name="Customer Escalation",
        version="1.0.0",
        description="Analyze and respond to a customer escalation with root cause and resolution plan.",
        category=MissionCategory.CUSTOMER_ESCALATION,
        tags=["customer", "support", "escalation", "ticket", "resolution"],
    ),
    objective_template=(
        "Analyze and respond to a customer escalation for {organization}. "
        "Customer: {customer_name}. "
        "Severity: {severity}. "
        "Issue description: {issue_description}. "
        "Affected services: {affected_services}. "
        "Business impact: {business_impact}. "
        "SLA: {sla}. "
        "Produce a structured escalation response including: issue summary, "
        "root cause analysis, resolution plan, workaround, "
        "expected timeline, customer communication template, "
        "and preventive measures."
    ),
    objectives=[
        "Analyze the escalation issue and business impact",
        "Perform root cause analysis",
        "Document resolution steps and workaround",
        "Define expected resolution timeline",
        "Prepare customer communication",
        "Recommend preventive measures",
    ],
    required_workers=[WorkerType.BROWSER],
    required_connectors=[ConnectorType.RABBITMQ, ConnectorType.REDIS, ConnectorType.NEO4J],
    required_approvals=GovernanceLevel.MEDIUM,
    success_criteria=[
        SuccessCriterion(description="Root cause identified"),
        SuccessCriterion(description="Resolution plan with timeline"),
        SuccessCriterion(description="Workaround documented"),
        SuccessCriterion(description="Customer communication drafted"),
        SuccessCriterion(description="Preventive measures recommended"),
    ],
    failure_recovery=FailureRecovery(
        description="Escalate to senior support engineer. Keep customer informed.",
        rollback_action="Apply workaround to restore service. Document root cause findings.",
    ),
    retry_policy=RetryPolicy(max_retries=2, backoff_seconds=3.0),
    audit_requirements=AuditLevel.DETAILED,
    needs_browser=True,
)

# ==============================================================================
# 10. DISASTER RECOVERY
# ==============================================================================

DISASTER_RECOVERY = MissionDefinition(
    metadata=MissionMetadata(
        id="enterprise.disaster_recovery",
        name="Disaster Recovery",
        version="1.0.0",
        description="Design and document a disaster recovery plan with RTO/RPO targets and validation.",
        category=MissionCategory.DISASTER_RECOVERY,
        tags=["disaster", "recovery", "dr", "business-continuity", "rto", "rpo"],
    ),
    objective_template=(
        "Design a disaster recovery plan for {organization}. "
        "Scope: {scope}. "
        "RTO target: {rto}. "
        "RPO target: {rpo}. "
        "Critical systems: {critical_systems}. "
        "Failure scenarios to cover: {failure_scenarios}. "
        "Produce a comprehensive DR plan covering: recovery architecture, "
        "failover procedures for each scenario, recovery runbooks, "
        "data replication strategy, backup validation, "
        "communication plan, and DR test schedule."
    ),
    objectives=[
        "Design recovery architecture for all failure scenarios",
        "Document failover procedures step by step",
        "Define data replication and backup strategy",
        "Create recovery runbooks per scenario",
        "Plan DR testing schedule and success criteria",
        "Document communication and escalation procedures",
    ],
    required_workers=[WorkerType.BROWSER],
    required_connectors=[ConnectorType.RABBITMQ, ConnectorType.REDIS, ConnectorType.NEO4J],
    required_approvals=GovernanceLevel.CRITICAL,
    success_criteria=[
        SuccessCriterion(description="RTO targets achievable for all scenarios"),
        SuccessCriterion(description="RPO targets achievable for all scenarios"),
        SuccessCriterion(description="Failover procedures documented"),
        SuccessCriterion(description="Recovery runbooks complete"),
        SuccessCriterion(description="DR test schedule defined"),
        SuccessCriterion(description="Backup validation plan documented"),
    ],
    failure_recovery=FailureRecovery(
        description="Document partial DR plan. Escalate to business continuity lead.",
        rollback_action="Activate DR hot site if available. Initiate emergency change process.",
    ),
    retry_policy=RetryPolicy(max_retries=2, backoff_seconds=5.0),
    audit_requirements=AuditLevel.FULL,
    needs_browser=True,
)


# ==============================================================================
# REGISTRY
# ==============================================================================

MISSION_REGISTRY: dict[str, MissionDefinition] = {
    "software_release": SOFTWARE_RELEASE,
    "incident_response": INCIDENT_RESPONSE,
    "executive_research": EXECUTIVE_RESEARCH,
    "compliance_audit": COMPLIANCE_AUDIT,
    "change_management": CHANGE_MANAGEMENT,
    "infrastructure_deployment": INFRASTRUCTURE_DEPLOYMENT,
    "security_investigation": SECURITY_INVESTIGATION,
    "knowledge_discovery": KNOWLEDGE_DISCOVERY,
    "customer_escalation": CUSTOMER_ESCALATION,
    "disaster_recovery": DISASTER_RECOVERY,
}


def get_mission(mission_id: str) -> MissionDefinition | None:
    direct = MISSION_REGISTRY.get(mission_id)
    if direct is not None:
        return direct
    for key, mission in MISSION_REGISTRY.items():
        if mission.metadata.id == mission_id:
            return mission
    return None


def list_missions() -> list[dict]:
    return [m.to_dict() for m in MISSION_REGISTRY.values()]
