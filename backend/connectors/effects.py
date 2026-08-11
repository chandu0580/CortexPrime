"""The V1 connector effect gate — Phase 6.1, Law L1 (One Plane of Action).

Why this exists
-----------------
Phase 6.1 discovery classified every side-effecting path in the repository and
found ~90 write-capable connector methods reachable from unauthenticated HTTP
routes and always-on background loops, with no capability, no authorization,
no tenant, and no governed audit. The governed invocation gateway is the only
sanctioned path to a provider write; these methods predate it.

This module is the chokepoint that makes those writes refuse by default. It is
deliberately *not* a second governance system: a write that is not permitted
raises the same :class:`LegacyExecutionRefused`, under the same
``CORTEXPRIME_ENABLE_LEGACY_EXECUTION`` flag, with the same message, as every
other quarantined V1 execution surface. One flag, one mechanism, one inventory.

Classification is fail-closed
-------------------------------
Every known operation of every V1 connector is listed here explicitly, split
into the write set and the full known set. An operation that is not listed —
a new method added to a connector, a renamed method, a connector this module
has never heard of — classifies as a WRITE and is refused. The alternative
(pattern-matching verbs and letting unknowns through) is how a new
``do_deploy`` method becomes an ungoverned side effect nobody classified.

Reads pass. Read operations are still ungoverned outbound calls with a
process-wide credential — that is recorded honestly in the Phase 6.1 map —
but they expose no capability to change a provider, and sweeping them in
would take the dashboards and watchers down with nothing gained for L1.

Enforcement placement
-----------------------
:func:`assert_effect_permitted` is the first statement of
``BaseConnector._execute`` (15 of 19 connectors route every operation through
it) and of the three bypass seams found by discovery: ``ArgoCDConnector._post``
(all three ArgoCD writes), ``GitHubConnector.graphql_request`` (arbitrary
GraphQL, which can carry any mutation), and ``TerraformConnector._run``
(every terraform invocation is a subprocess with the process environment —
all of them gate, reads included, because a subprocess is a machine side
effect regardless of the verb).
"""

from __future__ import annotations

from typing import Dict, FrozenSet

from backend.api.legacy_execution_boundary import guard_legacy_internal

__all__ = [
    "EFFECT_WRITE",
    "EFFECT_READ",
    "WRITE_OPERATIONS",
    "KNOWN_OPERATIONS",
    "classify_effect",
    "assert_effect_permitted",
]

EFFECT_WRITE = "write"
EFFECT_READ = "read"

#: Write-capable operations per connector type. Sourced from the Phase 6.1
#: side-effect inventory (docs/PHASE_6_1_IMPLEMENTATION_MAP.md §2) and the
#: generated method inventory; every name was read in its connector module,
#: not inferred. ``graphql_request`` is a write because an arbitrary GraphQL
#: document can carry any mutation. Every terraform operation is a write
#: because every one spawns a subprocess.
WRITE_OPERATIONS: Dict[str, FrozenSet[str]] = {
    "github": frozenset({
        "archive_repository", "cancel_workflow_run", "create_branch",
        "create_commit_status", "create_deployment", "create_deployment_status",
        "create_issue", "create_pull_request", "create_pull_request_review",
        "create_release", "create_repository", "delete_release",
        "dismiss_pull_request_review", "dispatch_workflow", "graphql_request",
        "merge_pull_request", "remove_branch_protection", "rerun_failed_jobs",
        "rerun_workflow", "set_admin_enforcement", "submit_pull_request_review",
        "update_branch_protection", "update_file_contents", "update_issue",
    }),
    "gitlab_ci": frozenset({
        "cancel_job", "cancel_pipeline", "create_pipeline", "create_variable",
        "enable_project_runner", "play_job", "retry_job", "retry_pipeline",
        "update_variable",
    }),
    "jenkins": frozenset({"build_job", "cancel_queue_item", "stop_build"}),
    "circleci": frozenset({
        "approve_workflow", "cancel_pipeline", "cancel_workflow",
        "rerun_workflow", "trigger_pipeline",
    }),
    "azure_devops": frozenset({
        "cancel_pipeline", "create_work_item", "queue_pipeline",
        "update_work_item",
    }),
    "jira": frozenset({
        "add_comment", "assign_issue", "complete_sprint", "create_issue",
        "transition_issue", "update_issue",
    }),
    "confluence": frozenset({
        "create_comment", "create_page", "delete_page", "update_page",
    }),
    "notion": frozenset({
        "append_blocks", "archive_page", "create_database", "create_page",
        "update_page",
    }),
    "servicenow": frozenset({
        "approve_change_request", "create_change_request", "create_incident",
        "resolve_incident", "update_incident",
    }),
    "slack": frozenset({
        "create_channel", "invite_user", "send_message", "upload_file",
    }),
    "teams": frozenset({
        "create_channel", "create_meeting", "reply_to_message", "send_message",
    }),
    "docker": frozenset({
        "prune_images", "pull_image", "remove_image", "restart_container",
    }),
    "kubernetes": frozenset(),
    "argocd": frozenset({
        "refresh_application", "rollback_application", "sync_application",
    }),
    "prometheus": frozenset(),
    "loki": frozenset(),
    "grafana": frozenset(),
    "opentelemetry": frozenset(),
    "terraform": frozenset({
        "apply", "destroy", "fmt", "get_version", "import_resource", "init",
        "output", "plan", "providers", "refresh", "show", "state_list",
        "state_rm", "state_show", "validate", "workspace_delete",
        "workspace_list", "workspace_new", "workspace_select", "workspace_show",
    }),
}

#: Every operation this module has classified, write or read. An operation
#: absent from its connector's entry — or a connector absent entirely —
#: classifies as WRITE. This is the fail-closed rule: new capability is
#: refused until someone classifies it, which is a code review, not an outage.
KNOWN_OPERATIONS: Dict[str, FrozenSet[str]] = {
    "github": WRITE_OPERATIONS["github"] | frozenset({
        "check_credential", "get_admin_enforcement", "get_branch_protection",
        "get_combined_status", "get_commit", "get_deployment",
        "get_file_contents", "get_issue", "get_last_successful_deployment",
        "get_latest_release", "get_pull_request", "get_pull_request_review",
        "get_rate_limit", "get_release", "get_release_by_id", "get_repository",
        "get_workflow", "get_workflow_run", "get_workflow_runs",
        "list_branches", "list_check_runs", "list_check_suites",
        "list_commit_statuses", "list_dependabot_alerts",
        "list_deployment_statuses", "list_deployments", "list_jobs_for_run",
        "list_pull_request_reviewers", "list_pull_request_reviews",
        "list_pull_requests", "list_releases", "list_repositories",
        "list_repository_events", "list_repository_tags", "list_workflow_runs",
        "list_workflows", "wait_if_needed",
    }),
    "gitlab_ci": WRITE_OPERATIONS["gitlab_ci"] | frozenset({
        "check_credential", "download_artifact", "get_commit",
        "get_commit_diff", "get_commit_with_diff", "get_job", "get_job_log",
        "get_last_successful_deployment", "get_pipeline",
        "get_pipeline_stages", "get_project", "get_runner", "list_deployments",
        "list_job_artifacts", "list_jobs", "list_merge_request_pipelines",
        "list_pipelines", "list_projects", "list_runners", "list_variables",
    }),
    "jenkins": WRITE_OPERATIONS["jenkins"] | frozenset({
        "get_build", "get_build_log", "get_build_stages", "get_health",
        "get_job", "get_job_config", "get_queue", "list_agents", "list_builds",
        "list_folders", "list_jobs", "list_pipelines",
    }),
    "circleci": WRITE_OPERATIONS["circleci"] | frozenset({
        "get_job", "get_job_artifacts", "get_job_details", "get_pipeline",
        "get_project", "get_project_insights", "get_workflow",
        "get_workflow_insights", "get_workflow_summary", "list_jobs",
        "list_pipelines", "list_projects", "list_workflows",
    }),
    "azure_devops": WRITE_OPERATIONS["azure_devops"] | frozenset({
        "get_pipeline_run", "get_pull_requests", "get_work_item",
        "list_pipelines", "list_projects", "list_repositories",
        "list_work_items",
    }),
    "jira": WRITE_OPERATIONS["jira"] | frozenset({"check_credential", "get_issue"}),
    "confluence": WRITE_OPERATIONS["confluence"] | frozenset({
        "get_page", "get_space", "list_pages", "list_spaces", "search_pages",
    }),
    "notion": WRITE_OPERATIONS["notion"] | frozenset({
        "get_page", "list_blocks", "list_pages", "list_users",
        "query_database", "search",
    }),
    "servicenow": WRITE_OPERATIONS["servicenow"] | frozenset({
        "get_incident", "list_change_requests", "list_incidents",
    }),
    "slack": WRITE_OPERATIONS["slack"] | frozenset({
        "list_channels", "list_messages",
    }),
    "teams": WRITE_OPERATIONS["teams"] | frozenset({
        "get_channel", "get_team", "list_channels", "list_messages",
        "list_teams",
    }),
    "docker": WRITE_OPERATIONS["docker"] | frozenset({
        "df", "get_container", "get_container_logs", "get_container_stats",
        "get_image", "get_image_history", "get_info",
        "get_registry_repositories", "get_version", "get_volume",
        "list_compose_projects", "list_containers", "list_images",
        "list_networks", "list_volumes", "search_registry",
    }),
    "kubernetes": frozenset({
        "get_cluster", "get_deployment", "get_node", "get_pod",
        "get_pod_logs", "list_clusters", "list_deployments", "list_events",
        "list_namespaces", "list_nodes", "list_pods", "list_pvcs",
        "list_services",
    }),
    "argocd": WRITE_OPERATIONS["argocd"] | frozenset({
        "get_application", "get_application_events",
        "get_application_resource_tree", "get_application_revisions",
        "get_revision_metadata", "health_check", "list_applications",
        "list_clusters", "list_projects", "list_repositories",
    }),
    "prometheus": frozenset({
        "alerts", "health_check", "label_values", "labels", "query",
        "query_range", "rules", "series", "targets",
    }),
    "loki": frozenset({
        "health_check", "label_values", "labels", "query", "query_range",
        "series", "tail",
    }),
    "grafana": frozenset({
        "frontend_settings", "get_dashboard", "get_datasource",
        "get_datasource_by_name", "health_check", "list_alerts",
        "list_annotations", "list_datasources", "list_folders", "org",
        "ruler_rules", "search_dashboards",
    }),
    "opentelemetry": frozenset({"decode_json", "decode_protobuf"}),
    "terraform": WRITE_OPERATIONS["terraform"],
}


def classify_effect(connector_type: str, operation: str) -> str:
    """Classify one connector operation as a read or a write.

    Fail-closed: an operation this module cannot name is a WRITE.
    """
    known = KNOWN_OPERATIONS.get(connector_type)
    if known is None or operation not in known:
        return EFFECT_WRITE
    writes = WRITE_OPERATIONS.get(connector_type, frozenset())
    return EFFECT_WRITE if operation in writes else EFFECT_READ


def assert_effect_permitted(connector_type: str, operation: str) -> None:
    """Refuse a write-classified connector operation unless the legacy flag is set.

    Raises :class:`backend.api.legacy_execution_boundary.LegacyExecutionRefused`
    for writes while ``CORTEXPRIME_ENABLE_LEGACY_EXECUTION`` is unset — the
    identical refusal every other quarantined V1 surface produces. Reads return
    without ceremony.
    """
    if classify_effect(connector_type, operation) == EFFECT_READ:
        return
    guard_legacy_internal(f"connector:{connector_type}.{operation}")
