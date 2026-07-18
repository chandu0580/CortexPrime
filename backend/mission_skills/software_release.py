from __future__ import annotations

import logging

from backend.mission_skills.base import BaseMissionSkill
from backend.mission_skills.models import (
    ApprovalConfig,
    RetryPolicy,
    WorkflowDefinition,
    WorkflowStepDef,
)

log = logging.getLogger(__name__)


class SoftwareReleaseSkill(BaseMissionSkill):
    """
    Enterprise mission skill that executes a complete software release
    workflow via the GitHub connector.

    Defined as a declarative ``WorkflowDefinition`` — the Mission Skill
    Engine handles execution, persistence, retry, approval, replay,
    audit, and telemetry automatically.

    Workflow steps:

      1. create_release_branch   — ``create_branch`` on GitHub
      2. create_pull_request     — ``create_pull_request`` on GitHub
      3. wait_for_approval       — ApprovalQueue gate (optional)
      4. merge_pull_request      — ``merge_pull_request`` on GitHub
      5. create_github_release   — ``create_release`` on GitHub
      6. dispatch_release_workflow — ``dispatch_workflow`` on GitHub
    """

    skill_type = "software_release"

    def get_definition(self) -> WorkflowDefinition:
        return WorkflowDefinition(
            skill_type=self.skill_type,
            description="Create a GitHub release branch, PR, merge, tag release, and dispatch workflow.",
            steps=[
                WorkflowStepDef(
                    id="create_release_branch",
                    name="Create Release Branch",
                    connector="github",
                    operation="create_branch",
                    params={
                        "owner": "$params.owner",
                        "repo": "$params.repo",
                        "branch_name": "$params.branch_name",
                        "source_branch": "$params.base_branch",
                    },
                    retry=RetryPolicy(max_retries=2),
                    outputs={"branch": "$.ref"},
                ),
                WorkflowStepDef(
                    id="create_pull_request",
                    name="Create Pull Request",
                    connector="github",
                    operation="create_pull_request",
                    params={
                        "owner": "$params.owner",
                        "repo": "$params.repo",
                        "title": "$params.pr_title",
                        "body": "$params.pr_body",
                        "head": "$steps.create_release_branch.branch",
                        "base": "$params.base_branch",
                    },
                    outputs={"pr_number": "$.number", "pr_url": "$.html_url"},
                ),
                WorkflowStepDef(
                    id="wait_for_approval",
                    name="Wait for Approval",
                    connector=None,
                    operation="__approval__",
                    params={},
                    approval=ApprovalConfig(
                        required="$params.require_approval",
                        timeout=300,
                        risk_level="medium",
                        action="merge_release_pr",
                        description_template="Approve release PR for $params.owner/$params.repo",
                    ),
                ),
                WorkflowStepDef(
                    id="merge_pull_request",
                    name="Merge Pull Request",
                    connector="github",
                    operation="merge_pull_request",
                    params={
                        "owner": "$params.owner",
                        "repo": "$params.repo",
                        "pr_number": "$steps.create_pull_request.pr_number",
                    },
                    outputs={"merge_sha": "$.sha"},
                ),
                WorkflowStepDef(
                    id="create_github_release",
                    name="Create GitHub Release",
                    connector="github",
                    operation="create_release",
                    params={
                        "owner": "$params.owner",
                        "repo": "$params.repo",
                        "tag_name": "$params.tag_name",
                        "name": "$params.release_name",
                        "body": "$params.release_body",
                    },
                    outputs={"release_id": "$.id", "release_url": "$.html_url"},
                ),
                WorkflowStepDef(
                    id="dispatch_release_workflow",
                    name="Dispatch Release Workflow",
                    connector="github",
                    operation="dispatch_workflow",
                    params={
                        "owner": "$params.owner",
                        "repo": "$params.repo",
                        "workflow_id": "$params.workflow_id",
                        "ref": "$params.base_branch",
                        "inputs": {
                            "version": "$params.version",
                            "tag": "$params.tag_name",
                        },
                    },
                    retry=RetryPolicy(max_retries=1),
                ),
            ],
        )
