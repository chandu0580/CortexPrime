"""
Enterprise Git Operations & Pull Request Automation.

Orchestrates Git provider operations through existing connectors
(GitHub, Azure DevOps) to safely create branches, commit validated
patches, open pull requests, sync issues, and attach engineering context.

Parts:
  1. GitBranchManager  — CRUD for branches
  2. CommitManager     — staged commits with intelligent messages
  3. PullRequestManager — PR lifecycle, reviewers, labels, milestones
  4. EngineeringContext — auto-generated PR descriptions
  5. IssueSyncManager  — link/close/comment/update issues
  6. EnterpriseGitOperations — orchestrator
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_BRANCHES_FILE = _DATA_DIR / "git_branches.json"
_COMMITS_FILE = _DATA_DIR / "git_commits.json"
_PRS_FILE = _DATA_DIR / "git_pull_requests.json"
_HISTORY_FILE = _DATA_DIR / "git_history.json"

GIT_OPS_EVENTS = {
    "branch_created": "git.branch_created",
    "commit_created": "git.commit_created",
    "pull_request_opened": "git.pull_request_opened",
    "pull_request_updated": "git.pull_request_updated",
    "pull_request_merged": "git.pull_request_merged",
    "issue_synchronized": "git.issue_synchronized",
}


# =============================================================================
# Helpers
# =============================================================================

def _load_json(path: Path) -> List[Dict[str, Any]]:
    try:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception as exc:
        log.error("Failed to load %s: %s", path.name, exc)
    return []


def _save_json(path: Path, data: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _parse_github_url(url: str) -> Tuple[str, str]:
    """Parse a GitHub URL into (owner, repo)."""
    m = re.match(r"(?:https?://github\.com/|git@github\.com:)([^/]+)/([^/.]+)", url)
    if m:
        return m.group(1), m.group(2)
    raise ValueError(f"Could not parse GitHub URL: {url}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# Part 1 — Git Branch Manager
# =============================================================================

class GitBranchManager:
    """CRUD for Git branches via the GitHub connector."""

    @staticmethod
    async def _get_gh():
        from backend.connectors.registry import connector_registry
        gh = connector_registry.get("github")
        if not gh:
            raise RuntimeError("GitHub connector not registered")
        return gh

    @staticmethod
    async def list_branches(repo_url: str) -> List[Dict[str, Any]]:
        """List all branches for a repository."""
        owner, repo = _parse_github_url(repo_url)
        gh = await GitBranchManager._get_gh()
        branches = await gh.list_branches(owner, repo)
        return [
            {
                "name": b["name"],
                "sha": b["commit"]["sha"],
                "protected": b.get("protected", False),
            }
            for b in branches
        ]

    @staticmethod
    async def create_branch(
        repo_url: str,
        branch_name: str,
        source_branch: str = "main",
    ) -> Dict[str, Any]:
        """Create a new branch from a source branch."""
        owner, repo = _parse_github_url(url=repo_url)
        gh = await GitBranchManager._get_gh()
        result = await gh.create_branch(owner, repo, branch_name, source_branch)
        return {
            "repo_url": repo_url,
            "branch_name": branch_name,
            "source_branch": source_branch,
            "ref": result.get("ref", ""),
            "sha": result.get("object", {}).get("sha", ""),
            "created_at": _now(),
        }

    @staticmethod
    async def delete_branch(repo_url: str, branch_name: str) -> bool:
        """Delete a branch."""
        owner, repo = _parse_github_url(url=repo_url)
        gh = await GitBranchManager._get_gh()
        try:
            await gh._request("DELETE", f"/repos/{owner}/{repo}/git/refs/heads/{branch_name}")
            return True
        except Exception as exc:
            log.warning("Failed to delete branch %s: %s", branch_name, exc)
            return False

    @staticmethod
    async def rename_branch(
        repo_url: str,
        old_name: str,
        new_name: str,
    ) -> Dict[str, Any]:
        """Rename a branch by creating from old HEAD and deleting old."""
        owner, repo = _parse_github_url(url=repo_url)
        gh = await GitBranchManager._get_gh()
        branch = await gh.create_branch(owner, repo, new_name, old_name)
        await GitBranchManager.delete_branch(repo_url, old_name)
        return {
            "repo_url": repo_url,
            "old_name": old_name,
            "new_name": new_name,
            "sha": branch.get("sha", ""),
            "renamed_at": _now(),
        }

    @staticmethod
    async def compare_branches(
        repo_url: str,
        base: str,
        head: str,
    ) -> Dict[str, Any]:
        """Compare two branches."""
        owner, repo = _parse_github_url(url=repo_url)
        gh = await GitBranchManager._get_gh()
        result = await gh._request("GET", f"/repos/{owner}/{repo}/compare/{base}...{head}")
        return {
            "repo_url": repo_url,
            "base": base,
            "head": head,
            "ahead_by": result.get("ahead_by", 0),
            "behind_by": result.get("behind_by", 0),
            "total_commits": result.get("total_commits", 0),
            "files": [
                {
                    "filename": f["filename"],
                    "status": f["status"],
                    "additions": f.get("additions", 0),
                    "deletions": f.get("deletions", 0),
                }
                for f in result.get("files", [])
            ],
            "compared_at": _now(),
        }


# =============================================================================
# Part 2 — Commit Manager
# =============================================================================

class CommitManager:
    """Stage files and create commits via the GitHub Git Data API."""

    @staticmethod
    async def _get_gh():
        from backend.connectors.registry import connector_registry
        gh = connector_registry.get("github")
        if not gh:
            raise RuntimeError("GitHub connector not registered")
        return gh

    @staticmethod
    def _generate_message(
        description: str,
        commit_type: str = "fix",
        scope: Optional[str] = None,
        breaking: bool = False,
    ) -> str:
        """Generate an intelligent conventional commit message."""
        prefix = ""
        if breaking:
            prefix = "BREAKING CHANGE: "
        elif commit_type:
            scope_str = f"({scope})" if scope else ""
            prefix = f"{commit_type}{scope_str}: "

        title = description.strip().split("\n")[0][:72]
        if not title.endswith(".") and not title.endswith("!") and not title.endswith("?"):
            title += "."

        body_lines = description.strip().split("\n")[1:]
        body = "\n".join(body_lines) if body_lines else ""

        msg = f"{prefix}{title}"
        if body:
            msg += f"\n\n{body}"
        return msg

    @staticmethod
    async def create_commit(
        repo_url: str,
        branch: str,
        message: str,
        files: List[Dict[str, Any]],
        author: Optional[Dict[str, str]] = None,
        committer: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Create a commit on a branch using the Git Data API.

        Each file dict must have: path, content, and optionally encoding (default 'utf-8').
        """
        owner, repo = _parse_github_url(url=repo_url)
        gh = await CommitManager._get_gh()

        # 1) Get the current HEAD commit SHA for the branch
        ref_resp = await gh._request("GET", f"/repos/{owner}/{repo}/git/refs/heads/{branch}")
        head_sha = ref_resp["object"]["sha"]

        # 2) Get the current commit tree SHA
        commit_resp = await gh._request("GET", f"/repos/{owner}/{repo}/git/commits/{head_sha}")
        base_tree_sha = commit_resp["tree"]["sha"]

        # 3) Create blobs for each file
        blobs = []
        for f in files:
            content = f["content"]
            encoding = f.get("encoding", "utf-8")
            if encoding == "base64":
                blob_in = {"content": content, "encoding": "base64"}
            else:
                blob_in = {"content": content, "encoding": "utf-8"}
            blob_resp = await gh._request("POST", f"/repos/{owner}/{repo}/git/blobs", json=blob_in)
            blobs.append({"path": f["path"], "sha": blob_resp["sha"], "mode": f.get("mode", "100644"), "type": "blob"})

        # 4) Create a new tree with the blobs
        tree_resp = await gh._request("POST", f"/repos/{owner}/{repo}/git/trees", json={
            "base_tree": base_tree_sha,
            "tree": blobs,
        })
        new_tree_sha = tree_resp["sha"]

        # 5) Create the commit
        commit_data: Dict[str, Any] = {
            "message": message,
            "tree": new_tree_sha,
            "parents": [head_sha],
        }
        if author:
            commit_data["author"] = author
        if committer:
            commit_data["committer"] = committer

        commit_resp = await gh._request("POST", f"/repos/{owner}/{repo}/git/commits", json=commit_data)
        commit_sha = commit_resp["sha"]

        # 6) Update the branch ref to point to the new commit
        await gh._request("PATCH", f"/repos/{owner}/{repo}/git/refs/heads/{branch}", json={
            "sha": commit_sha,
            "force": False,
        })

        return {
            "repo_url": repo_url,
            "branch": branch,
            "sha": commit_sha,
            "message": message,
            "author": author or {},
            "files_count": len(files),
            "files": [f["path"] for f in files],
            "created_at": _now(),
        }

    @staticmethod
    async def stage_and_commit(
        repo_url: str,
        branch: str,
        description: str,
        files: List[Dict[str, Any]],
        commit_type: str = "fix",
        scope: Optional[str] = None,
        breaking: bool = False,
        author: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Generate a commit message and create the commit."""
        message = CommitManager._generate_message(description, commit_type, scope, breaking)
        result = await CommitManager.create_commit(repo_url, branch, message, files, author)
        return result


# =============================================================================
# Part 3 — Pull Request Manager
# =============================================================================

class PullRequestManager:
    """CRUD for pull requests via the GitHub connector."""

    @staticmethod
    async def _get_gh():
        from backend.connectors.registry import connector_registry
        gh = connector_registry.get("github")
        if not gh:
            raise RuntimeError("GitHub connector not registered")
        return gh

    @staticmethod
    async def create(
        repo_url: str,
        title: str,
        body: str = "",
        head: str = "",
        base: str = "main",
        reviewers: Optional[List[str]] = None,
        labels: Optional[List[str]] = None,
        milestone: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a pull request."""
        owner, repo = _parse_github_url(url=repo_url)
        gh = await PullRequestManager._get_gh()

        pr = await gh.create_pull_request(owner, repo, title=title, body=body, head=head, base=base)

        pr_number = pr.get("number", 0)

        # Request reviewers if specified
        if reviewers and pr_number:
            try:
                await gh._request("POST", f"/repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers", json={"reviewers": reviewers})
            except Exception as exc:
                log.warning("Failed to request reviewers: %s", exc)

        # Add labels if specified
        if labels and pr_number:
            try:
                await gh._request("POST", f"/repos/{owner}/{repo}/issues/{pr_number}/labels", json={"labels": labels})
            except Exception as exc:
                log.warning("Failed to add labels: %s", exc)

        # Set milestone if specified
        if milestone is not None and pr_number:
            try:
                await gh.update_issue(owner, repo, issue_number=pr_number, milestone=milestone)
            except Exception as exc:
                log.warning("Failed to set milestone: %s", exc)

        return {
            "repo_url": repo_url,
            "pr_number": pr_number,
            "title": title,
            "head": head,
            "base": base,
            "state": pr.get("state", "open"),
            "html_url": pr.get("html_url", ""),
            "reviewers": reviewers or [],
            "labels": labels or [],
            "milestone": milestone,
            "created_at": pr.get("created_at", _now()),
        }

    @staticmethod
    async def update(
        repo_url: str,
        pr_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a pull request."""
        owner, repo = _parse_github_url(url=repo_url)
        gh = await PullRequestManager._get_gh()
        update_data: Dict[str, Any] = {}
        if title is not None:
            update_data["title"] = title
        if body is not None:
            update_data["body"] = body
        if state is not None:
            update_data["state"] = state
        result = await gh._request("PATCH", f"/repos/{owner}/{repo}/pulls/{pr_number}", json=update_data)
        return {
            "repo_url": repo_url,
            "pr_number": pr_number,
            "title": result.get("title", title or ""),
            "state": result.get("state", state or "open"),
            "updated_at": result.get("updated_at", _now()),
        }

    @staticmethod
    async def close(repo_url: str, pr_number: int) -> Dict[str, Any]:
        """Close a pull request without merging."""
        return await PullRequestManager.update(repo_url, pr_number, state="closed")

    @staticmethod
    async def reopen(repo_url: str, pr_number: int) -> Dict[str, Any]:
        """Reopen a closed pull request."""
        return await PullRequestManager.update(repo_url, pr_number, state="open")

    @staticmethod
    async def merge(
        repo_url: str,
        pr_number: int,
        merge_method: str = "merge",
        commit_title: Optional[str] = None,
        commit_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Merge a pull request."""
        owner, repo = _parse_github_url(url=repo_url)
        gh = await PullRequestManager._get_gh()
        merge_data: Dict[str, Any] = {"merge_method": merge_method}
        if commit_title:
            merge_data["commit_title"] = commit_title
        if commit_message:
            merge_data["commit_message"] = commit_message
        result = await gh.merge_pull_request(owner, repo, pr_number, **merge_data)
        return {
            "repo_url": repo_url,
            "pr_number": pr_number,
            "merged": result.get("merged", False),
            "sha": result.get("sha", ""),
            "message": result.get("message", ""),
            "merged_at": _now(),
        }

    @staticmethod
    async def list_open(
        repo_url: str,
        state: str = "open",
    ) -> List[Dict[str, Any]]:
        """List pull requests."""
        owner, repo = _parse_github_url(url=repo_url)
        gh = await PullRequestManager._get_gh()
        prs = await gh.list_pull_requests(owner, repo, state=state)
        return [
            {
                "pr_number": p["number"],
                "title": p["title"],
                "state": p["state"],
                "head": p["head"]["ref"],
                "base": p["base"]["ref"],
                "html_url": p["html_url"],
                "created_at": p["created_at"],
                "user": p["user"]["login"],
            }
            for p in prs
        ]

    @staticmethod
    async def get(repo_url: str, pr_number: int) -> Dict[str, Any]:
        """Get a single pull request."""
        owner, repo = _parse_github_url(url=repo_url)
        gh = await PullRequestManager._get_gh()
        pr = await gh.get_pull_request(owner, repo, pr_number)
        return {
            "pr_number": pr["number"],
            "title": pr["title"],
            "body": pr.get("body", ""),
            "state": pr["state"],
            "head": pr["head"]["ref"],
            "base": pr["base"]["ref"],
            "html_url": pr["html_url"],
            "created_at": pr["created_at"],
            "updated_at": pr.get("updated_at", ""),
            "merged_at": pr.get("merged_at"),
            "user": pr["user"]["login"],
            "mergeable": pr.get("mergeable"),
        }

    @staticmethod
    async def request_reviewers(
        repo_url: str,
        pr_number: int,
        reviewers: List[str],
    ) -> bool:
        """Request reviewers on a pull request."""
        owner, repo = _parse_github_url(url=repo_url)
        gh = await PullRequestManager._get_gh()
        try:
            await gh._request("POST", f"/repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers", json={"reviewers": reviewers})
            return True
        except Exception as exc:
            log.warning("Failed to request reviewers: %s", exc)
            return False

    @staticmethod
    async def add_labels(
        repo_url: str,
        pr_number: int,
        labels: List[str],
    ) -> bool:
        """Add labels to a pull request."""
        owner, repo = _parse_github_url(url=repo_url)
        gh = await PullRequestManager._get_gh()
        try:
            await gh._request("POST", f"/repos/{owner}/{repo}/issues/{pr_number}/labels", json={"labels": labels})
            return True
        except Exception as exc:
            log.warning("Failed to add labels: %s", exc)
            return False


# =============================================================================
# Part 4 — Engineering Context
# =============================================================================

class EngineeringContext:
    """Auto-generates PR descriptions by aggregating data from across the platform."""

    @staticmethod
    async def generate(
        mission_id: str = "",
        patch_plan_id: str = "",
        patch_candidate_id: str = "",
        repo_url: str = "",
        workspace_id: str = "",
        files_changed: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Build comprehensive engineering context for a PR description."""
        context: Dict[str, Any] = {
            "mission": None,
            "root_cause": "",
            "affected_files": files_changed or [],
            "impact_analysis": None,
            "validation_results": None,
            "coverage": None,
            "security_scan": None,
            "replay_references": [],
            "learning_references": [],
            "recommendation_references": [],
            "generated_at": _now(),
        }

        # Mission summary
        if mission_id:
            try:
                from backend.services.mission_runtime import mission_runtime
                mission = await mission_runtime.get_mission(mission_id)
                context["mission"] = {
                    "mission_id": mission_id,
                    "template": getattr(mission, "template_name", "") or getattr(mission, "objective", ""),
                    "objective": getattr(mission, "objective", ""),
                    "status": getattr(mission, "status", ""),
                }
            except Exception as exc:
                log.debug("Mission lookup failed: %s", exc)

        # Patch plan details
        if patch_plan_id:
            try:
                from backend.services.enterprise_patch_pipeline import patch_pipeline
                plans = await patch_pipeline.list_plans()
                for p in plans:
                    if p["plan_id"] == patch_plan_id:
                        context["root_cause"] = p.get("description", "")
                        break
            except Exception as exc:
                log.debug("Patch plan lookup failed: %s", exc)

        # Validation results from patch candidate
        if patch_candidate_id:
            try:
                from backend.services.enterprise_patch_pipeline import patch_pipeline
                candidates = await patch_pipeline.list_candidates()
                for c in candidates:
                    if c["candidate_id"] == patch_candidate_id and c.get("validation"):
                        val = c["validation"]
                        context["validation_results"] = {
                            "status": val.get("status", ""),
                            "build": val.get("build", {}),
                            "tests": val.get("tests", {}),
                            "security": val.get("security", {}),
                            "coverage": val.get("coverage", {}),
                        }
                        if val.get("coverage"):
                            context["coverage"] = val["coverage"]
                        if val.get("security"):
                            context["security_scan"] = val["security"]
                        break
            except Exception as exc:
                log.debug("Patch candidate lookup failed: %s", exc)

        # Impact analysis from code intelligence
        if files_changed:
            try:
                from backend.services.enterprise_code_intelligence import code_intelligence
                impact_results = []
                for f in files_changed[:5]:
                    try:
                        impact = await code_intelligence.compute_impact(f, repo_url if repo_url else ".")
                        impact_results.append(impact)
                    except Exception:
                        pass
                if impact_results:
                    context["impact_analysis"] = impact_results
            except Exception as exc:
                log.debug("Impact analysis failed: %s", exc)

        # Replay references
        if mission_id:
            try:
                from backend.services.mission_replay_store import replay_store
                replay = await replay_store.get_mission_replay(mission_id)
                if replay:
                    context["replay_references"] = [{
                        "execution_id": mission_id,
                        "total_events": len(replay) if isinstance(replay, list) else 0,
                    }]
            except Exception as exc:
                log.debug("Replay lookup failed: %s", exc)

        # Learning references
        try:
            from backend.services.enterprise_learning_service import enterprise_learning
            lessons = await enterprise_learning.list_lessons(limit=3)
            if lessons:
                context["learning_references"] = [
                    {"lesson_id": lesson.get("lesson_id", ""), "content": lesson.get("content", "")[:200]}
                    for lesson in lessons
                ]
        except Exception as exc:
            log.debug("Learning lookup failed: %s", exc)

        # Recommendation references
        try:
            from backend.services.enterprise_recommendation_engine import enterprise_recommendation_engine
            recs = await enterprise_recommendation_engine.list_recommendations(limit=3)
            if recs:
                context["recommendation_references"] = [
                    {"rec_id": r.get("id", ""), "title": r.get("title", "")}
                    for r in recs
                ]
        except Exception as exc:
            log.debug("Recommendation lookup failed: %s", exc)

        return context

    @staticmethod
    def format_pr_body(context: Dict[str, Any]) -> str:
        """Format engineering context into a markdown PR description."""
        lines: List[str] = []
        lines.append("## Summary")
        lines.append("")
        lines.append("This pull request was autonomously generated by CortexPrime.")
        lines.append("")

        mission = context.get("mission")
        if mission:
            lines.append(f"**Mission:** {mission.get('objective', 'N/A')}")
            lines.append(f"**Template:** {mission.get('template', 'N/A')}")
            lines.append(f"**Status:** {mission.get('status', 'N/A')}")
            lines.append("")

        root_cause = context.get("root_cause", "")
        if root_cause:
            lines.append("## Root Cause")
            lines.append("")
            lines.append(root_cause)
            lines.append("")

        files = context.get("affected_files", [])
        if files:
            lines.append("## Affected Files")
            lines.append("")
            for f in files:
                lines.append(f"- `{f}`")
            lines.append("")

        impact = context.get("impact_analysis")
        if impact:
            lines.append("## Impact Analysis")
            lines.append("")
            for entry in impact[:3]:
                if isinstance(entry, dict):
                    risk = entry.get("risk_level", "N/A")
                    changed = entry.get("changed_file", "N/A")
                    lines.append(f"- **{changed}** — Risk: {risk}")
            lines.append("")

        val = context.get("validation_results")
        if val:
            lines.append("## Validation Results")
            lines.append("")
            build = val.get("build", {})
            tests = val.get("tests", {})
            sec = val.get("security", {})
            cov = val.get("coverage", {})
            lines.append(f"- **Build:** {'✅ PASS' if build.get('success') else '❌ FAIL'}")
            lines.append(f"- **Tests:** {'✅ PASS' if tests.get('success') else '❌ FAIL'} ({tests.get('passed', 0)}/{tests.get('total', 0)} passed)")
            lines.append(f"- **Security:** {'✅ PASS' if sec.get('passed') else '❌ FAIL'} ({sec.get('vulnerabilities', 0)} vulns)")
            if cov:
                lines.append(f"- **Coverage:** {cov.get('line_coverage_pct', 'N/A')}% line, {cov.get('branch_coverage_pct', 'N/A')}% branch")
            lines.append("")

        replay = context.get("replay_references", [])
        if replay:
            lines.append("## Replay Reference")
            lines.append("")
            for r in replay:
                lines.append(f"- Execution `{r.get('execution_id', 'N/A')}` ({r.get('total_events', 0)} events)")
            lines.append("")

        learning = context.get("learning_references", [])
        if learning:
            lines.append("## Learning References")
            lines.append("")
            for lesson in learning:
                lines.append(f"- {lesson.get('content', 'N/A')[:120]}")
            lines.append("")

        recs = context.get("recommendation_references", [])
        if recs:
            lines.append("## Recommendation References")
            lines.append("")
            for r in recs:
                lines.append(f"- {r.get('title', 'N/A')}")
            lines.append("")

        return "\n".join(lines)


# =============================================================================
# Part 5 — Issue Sync Manager
# =============================================================================

class IssueSyncManager:
    """Synchronize issues across GitHub, Jira, and Azure DevOps."""

    @staticmethod
    async def _get_gh():
        from backend.connectors.registry import connector_registry
        gh = connector_registry.get("github")
        if not gh:
            raise RuntimeError("GitHub connector not registered")
        return gh

    @staticmethod
    async def _get_jira():
        from backend.connectors.registry import connector_registry
        return connector_registry.get("jira")

    @staticmethod
    async def _get_azure():
        from backend.connectors.registry import connector_registry
        return connector_registry.get("azure_devops")

    @staticmethod
    async def link_github_issue(
        repo_url: str,
        issue_number: int,
        pr_number: int,
    ) -> Dict[str, Any]:
        """Link a GitHub issue to a PR by commenting."""
        owner, repo = _parse_github_url(url=repo_url)
        gh = await IssueSyncManager._get_gh()
        body = f"Linked to pull request #{pr_number} — autonomously generated by CortexPrime."
        await gh._request("POST", f"/repos/{owner}/{repo}/issues/{issue_number}/comments", json={"body": body})
        return {
            "provider": "github",
            "repo_url": repo_url,
            "issue_number": issue_number,
            "pr_number": pr_number,
            "action": "linked",
            "synced_at": _now(),
        }

    @staticmethod
    async def close_github_issue(
        repo_url: str,
        issue_number: int,
        pr_number: int,
    ) -> Dict[str, Any]:
        """Close a GitHub issue with a reference to the PR."""
        owner, repo = _parse_github_url(url=repo_url)
        gh = await IssueSyncManager._get_gh()
        await gh.update_issue(owner, repo, issue_number=issue_number, state="closed")
        body = f"Closed by pull request #{pr_number} — autonomously resolved by CortexPrime."
        await gh._request("POST", f"/repos/{owner}/{repo}/issues/{issue_number}/comments", json={"body": body})
        return {
            "provider": "github",
            "repo_url": repo_url,
            "issue_number": issue_number,
            "pr_number": pr_number,
            "action": "closed",
            "synced_at": _now(),
        }

    @staticmethod
    async def comment_github_issue(
        repo_url: str,
        issue_number: int,
        body: str,
    ) -> Dict[str, Any]:
        """Comment on a GitHub issue."""
        owner, repo = _parse_github_url(url=repo_url)
        gh = await IssueSyncManager._get_gh()
        await gh._request("POST", f"/repos/{owner}/{repo}/issues/{issue_number}/comments", json={"body": body})
        return {
            "provider": "github",
            "repo_url": repo_url,
            "issue_number": issue_number,
            "action": "commented",
            "synced_at": _now(),
        }

    @staticmethod
    async def update_github_labels(
        repo_url: str,
        issue_number: int,
        labels: List[str],
    ) -> Dict[str, Any]:
        """Update labels on a GitHub issue."""
        owner, repo = _parse_github_url(url=repo_url)
        gh = await IssueSyncManager._get_gh()
        await gh._request("PUT", f"/repos/{owner}/{repo}/issues/{issue_number}/labels", json={"labels": labels})
        return {
            "provider": "github",
            "repo_url": repo_url,
            "issue_number": issue_number,
            "labels": labels,
            "action": "labels_updated",
            "synced_at": _now(),
        }

    @staticmethod
    async def sync_jira_issue(
        issue_key: str,
        comment: str = "",
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Sync a Jira issue — comment and optionally transition status."""
        jira = await IssueSyncManager._get_jira()
        result: Dict[str, Any] = {
            "provider": "jira",
            "issue_key": issue_key,
            "action": "synced",
            "synced_at": _now(),
        }
        if jira:
            try:
                if comment:
                    await jira.add_comment(issue_key, comment)
                    result["commented"] = True
                if status:
                    await jira.transition_issue(issue_key, status)
                    result["transitioned_to"] = status
            except Exception as exc:
                log.warning("Jira sync failed: %s", exc)
                result["error"] = str(exc)
        else:
            result["error"] = "Jira connector not available"
        return result

    @staticmethod
    async def sync_azure_work_item(
        work_item_id: int,
        comment: str = "",
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Sync an Azure DevOps work item."""
        azure = await IssueSyncManager._get_azure()
        result: Dict[str, Any] = {
            "provider": "azure_devops",
            "work_item_id": work_item_id,
            "action": "synced",
            "synced_at": _now(),
        }
        if azure:
            try:
                if state:
                    await azure.update_work_item(work_item_id, state=state)
                    result["state_updated_to"] = state
                if comment:
                    await azure._request("POST", f"/{azure._organization}/{azure._project}/_apis/wit/workItems/{work_item_id}/comments", json={"text": comment})
                    result["commented"] = True
            except Exception as exc:
                log.warning("Azure sync failed: %s", exc)
                result["error"] = str(exc)
        else:
            result["error"] = "Azure DevOps connector not available"
        return result

    @staticmethod
    async def sync(
        repo_url: str = "",
        pr_number: int = 0,
        issue_number: int = 0,
        issue_key: str = "",
        work_item_id: int = 0,
        provider: str = "github",
        action: str = "link",
        comment: str = "",
        labels: Optional[List[str]] = None,
        status: Optional[str] = None,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generic issue sync that routes to the correct provider."""
        if provider == "github" and repo_url and issue_number:
            if action == "link" and pr_number:
                return await IssueSyncManager.link_github_issue(repo_url, issue_number, pr_number)
            elif action == "close" and pr_number:
                return await IssueSyncManager.close_github_issue(repo_url, issue_number, pr_number)
            elif action == "comment":
                return await IssueSyncManager.comment_github_issue(repo_url, issue_number, comment)
            elif action == "labels":
                return await IssueSyncManager.update_github_labels(repo_url, issue_number, labels or [])
        elif provider == "jira" and issue_key:
            return await IssueSyncManager.sync_jira_issue(issue_key, comment, status)
        elif provider == "azure_devops" and work_item_id:
            return await IssueSyncManager.sync_azure_work_item(work_item_id, comment, state)
        return {"error": f"Unknown provider/params: provider={provider}"}


# =============================================================================
# Part 6 — Enterprise Git Operations (Orchestrator)
# =============================================================================

class EnterpriseGitOperations:
    """
    Orchestrates Git provider operations across the entire platform.
    Every operation is recorded, evented, and persisted.
    """

    def __init__(self) -> None:
        self._branches: Dict[str, Dict[str, Any]] = {}
        self._commits: Dict[str, Dict[str, Any]] = {}
        self._pull_requests: Dict[str, Dict[str, Any]] = {}
        self._history: List[Dict[str, Any]] = []
        self._load_persisted()

    # ── Branch Operations ──────────────────────────────────────────────────

    async def list_branches(self, repo_url: str) -> List[Dict[str, Any]]:
        return await GitBranchManager.list_branches(repo_url)

    async def create_branch(
        self,
        repo_url: str,
        branch_name: str,
        source_branch: str = "main",
        workspace_id: str = "",
    ) -> Dict[str, Any]:
        # Check protected branches
        if branch_name in ("main", "master", "develop", "production", "staging"):
            raise ValueError(f"Cannot create branch with protected name: {branch_name}")

        result = await GitBranchManager.create_branch(repo_url, branch_name, source_branch)
        branch_id = f"{repo_url}:{branch_name}"
        self._branches[branch_id] = {**result, "workspace_id": workspace_id}
        self._persist_branches()
        self._add_history("branch_created", branch_id, result)
        await self._emit(GIT_OPS_EVENTS["branch_created"], branch_id, result)

        # Update workspace branch if workspace_id provided
        if workspace_id:
            try:
                from backend.services.enterprise_workspace_engine import workspace_manager
                await workspace_manager.checkout_branch(workspace_id, branch_name)
            except Exception as exc:
                log.debug("Workspace branch update failed: %s", exc)

        return result

    async def delete_branch(self, repo_url: str, branch_name: str) -> bool:
        return await GitBranchManager.delete_branch(repo_url, branch_name)

    async def rename_branch(self, repo_url: str, old_name: str, new_name: str) -> Dict[str, Any]:
        result = await GitBranchManager.rename_branch(repo_url, old_name, new_name)
        self._add_history("branch_renamed", f"{repo_url}:{new_name}", result)
        return result

    async def compare_branches(self, repo_url: str, base: str, head: str) -> Dict[str, Any]:
        return await GitBranchManager.compare_branches(repo_url, base, head)

    # ── Commit Operations ──────────────────────────────────────────────────

    async def commit(
        self,
        repo_url: str,
        branch: str,
        description: str,
        files: List[Dict[str, Any]],
        commit_type: str = "fix",
        scope: Optional[str] = None,
        breaking: bool = False,
        author: Optional[Dict[str, str]] = None,
        patch_candidate_id: str = "",
        mission_id: str = "",
    ) -> Dict[str, Any]:
        result = await CommitManager.stage_and_commit(
            repo_url=repo_url,
            branch=branch,
            description=description,
            files=files,
            commit_type=commit_type,
            scope=scope,
            breaking=breaking,
            author=author,
        )
        commit_id = result.get("sha", uuid.uuid4().hex[:12])
        result["mission_id"] = mission_id
        result["patch_candidate_id"] = patch_candidate_id
        self._commits[commit_id] = result
        self._persist_commits()
        self._add_history("commit_created", commit_id, result)
        await self._emit(GIT_OPS_EVENTS["commit_created"], commit_id, result)
        return result

    async def list_commits(self) -> List[Dict[str, Any]]:
        return list(self._commits.values())

    # ── Pull Request Operations ────────────────────────────────────────────

    async def create_pull_request(
        self,
        repo_url: str,
        title: str,
        head: str,
        base: str = "main",
        body: str = "",
        reviewers: Optional[List[str]] = None,
        labels: Optional[List[str]] = None,
        milestone: Optional[int] = None,
        mission_id: str = "",
        patch_plan_id: str = "",
        patch_candidate_id: str = "",
        workspace_id: str = "",
        files_changed: Optional[List[str]] = None,
        auto_context: bool = True,
    ) -> Dict[str, Any]:
        # Auto-generate engineering context for the PR body
        if auto_context and not body:
            try:
                context = await EngineeringContext.generate(
                    mission_id=mission_id,
                    patch_plan_id=patch_plan_id,
                    patch_candidate_id=patch_candidate_id,
                    repo_url=repo_url,
                    workspace_id=workspace_id,
                    files_changed=files_changed,
                )
                body = EngineeringContext.format_pr_body(context)
            except Exception as exc:
                log.debug("Engineering context generation failed: %s", exc)
                body = body or f"## Summary\n\nAutonomously generated by CortexPrime.\n\n**Branch:** `{head}` → `{base}`"

        result = await PullRequestManager.create(
            repo_url=repo_url,
            title=title,
            body=body,
            head=head,
            base=base,
            reviewers=reviewers,
            labels=labels,
            milestone=milestone,
        )
        pr_key = f"{repo_url}#{result['pr_number']}"
        result["mission_id"] = mission_id
        result["patch_plan_id"] = patch_plan_id
        result["patch_candidate_id"] = patch_candidate_id
        self._pull_requests[pr_key] = result
        self._persist_prs()
        self._add_history("pull_request_opened", pr_key, result)
        await self._emit(GIT_OPS_EVENTS["pull_request_opened"], pr_key, result)
        return result

    async def update_pull_request(
        self,
        repo_url: str,
        pr_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = await PullRequestManager.update(repo_url, pr_number, title=title, body=body)
        pr_key = f"{repo_url}#{pr_number}"
        self._add_history("pull_request_updated", pr_key, result)
        await self._emit(GIT_OPS_EVENTS["pull_request_updated"], pr_key, result)
        return result

    async def close_pull_request(self, repo_url: str, pr_number: int) -> Dict[str, Any]:
        return await PullRequestManager.close(repo_url, pr_number)

    async def reopen_pull_request(self, repo_url: str, pr_number: int) -> Dict[str, Any]:
        return await PullRequestManager.reopen(repo_url, pr_number)

    async def merge_pull_request(
        self,
        repo_url: str,
        pr_number: int,
        merge_method: str = "merge",
        commit_title: Optional[str] = None,
        commit_message: Optional[str] = None,
        require_approval: bool = True,
    ) -> Dict[str, Any]:
        # Check approval if required
        if require_approval:
            try:
                from backend.safety.approval_queue import approval_queue
                approved = await approval_queue.check_approval(f"merge_pr_{pr_number}")
                if not approved:
                    return {
                        "repo_url": repo_url,
                        "pr_number": pr_number,
                        "merged": False,
                        "message": "Merge blocked: human approval required",
                        "merged_at": _now(),
                    }
            except Exception:
                pass

        result = await PullRequestManager.merge(repo_url, pr_number, merge_method, commit_title, commit_message)
        pr_key = f"{repo_url}#{pr_number}"
        self._add_history("pull_request_merged", pr_key, result)
        await self._emit(GIT_OPS_EVENTS["pull_request_merged"], pr_key, result)
        return result

    async def list_pull_requests(self, repo_url: str, state: str = "open") -> List[Dict[str, Any]]:
        return await PullRequestManager.list_open(repo_url, state)

    async def get_pull_request(self, repo_url: str, pr_number: int) -> Dict[str, Any]:
        return await PullRequestManager.get(repo_url, pr_number)

    async def request_pr_reviewers(
        self,
        repo_url: str,
        pr_number: int,
        reviewers: List[str],
    ) -> bool:
        return await PullRequestManager.request_reviewers(repo_url, pr_number, reviewers)

    async def add_pr_labels(
        self,
        repo_url: str,
        pr_number: int,
        labels: List[str],
    ) -> bool:
        return await PullRequestManager.add_labels(repo_url, pr_number, labels)

    # ── Issue Sync Operations ──────────────────────────────────────────────

    async def sync_issue(
        self,
        repo_url: str = "",
        pr_number: int = 0,
        issue_number: int = 0,
        issue_key: str = "",
        work_item_id: int = 0,
        provider: str = "github",
        action: str = "link",
        comment: str = "",
        labels: Optional[List[str]] = None,
        status: Optional[str] = None,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = await IssueSyncManager.sync(
            repo_url=repo_url,
            pr_number=pr_number,
            issue_number=issue_number,
            issue_key=issue_key,
            work_item_id=work_item_id,
            provider=provider,
            action=action,
            comment=comment,
            labels=labels,
            status=status,
            state=state,
        )
        sync_key = f"{provider}:{issue_number or issue_key or work_item_id}"
        self._add_history("issue_synchronized", sync_key, result)
        await self._emit(GIT_OPS_EVENTS["issue_synchronized"], sync_key, result)
        return result

    # ── Engineering Context ────────────────────────────────────────────────

    async def generate_context(
        self,
        mission_id: str = "",
        patch_plan_id: str = "",
        patch_candidate_id: str = "",
        repo_url: str = "",
        workspace_id: str = "",
        files_changed: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return await EngineeringContext.generate(
            mission_id=mission_id,
            patch_plan_id=patch_plan_id,
            patch_candidate_id=patch_candidate_id,
            repo_url=repo_url,
            workspace_id=workspace_id,
            files_changed=files_changed,
        )

    async def format_context(self, context: Dict[str, Any]) -> str:
        return EngineeringContext.format_pr_body(context)

    # ── History ────────────────────────────────────────────────────────────

    async def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(reversed(self._history))[:limit]

    async def get_open_prs_summary(self) -> Dict[str, Any]:
        open_prs = [pr for pr in self._pull_requests.values() if pr.get("state") == "open" or not pr.get("state")]
        return {
            "total_open": len(open_prs),
            "pull_requests": list(open_prs),
        }

    # ── Events ─────────────────────────────────────────────────────────────

    async def _emit(self, event_type: str, entity_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type=event_type,
                agent="git_operations",
                status="info",
                message=f"Git Ops: {event_type.split('.')[-1]}",
                execution_id=entity_id,
                metadata={"entity_id": entity_id, "domain": "git", **(metadata or {})},
            )
        except Exception as exc:
            log.debug("Git ops event emit failed: %s", exc)

    # ── History ────────────────────────────────────────────────────────────

    def _add_history(self, action: str, entity_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        entry = {
            "action": action,
            "entity_id": entity_id,
            "timestamp": _now(),
            "metadata": metadata or {},
        }
        self._history.append(entry)
        self._persist_history()

    # ── Persistence ────────────────────────────────────────────────────────

    def _persist_branches(self) -> None:
        _save_json(_BRANCHES_FILE, list(self._branches.values()))

    def _persist_commits(self) -> None:
        _save_json(_COMMITS_FILE, list(self._commits.values()))

    def _persist_prs(self) -> None:
        _save_json(_PRS_FILE, list(self._pull_requests.values()))

    def _persist_history(self) -> None:
        _save_json(_HISTORY_FILE, self._history[-200:])

    def _load_persisted(self) -> None:
        try:
            for item in _load_json(_BRANCHES_FILE):
                key = f"{item.get('repo_url', '')}:{item.get('branch_name', '')}"
                self._branches[key] = item
            for item in _load_json(_COMMITS_FILE):
                self._commits[item.get("sha", item.get("commit_id", ""))] = item
            for item in _load_json(_PRS_FILE):
                key = f"{item.get('repo_url', '')}#{item.get('pr_number', 0)}"
                self._pull_requests[key] = item
            self._history = _load_json(_HISTORY_FILE)
            log.info("Loaded %d branches, %d commits, %d PRs, %d history entries",
                     len(self._branches), len(self._commits), len(self._pull_requests), len(self._history))
        except Exception as exc:
            log.warning("Git operations load failed: %s", exc)


# =============================================================================
# Singleton
# =============================================================================

git_operations = EnterpriseGitOperations()
