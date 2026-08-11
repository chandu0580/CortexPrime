"""
Enterprise Connector API Routes
================================

Provides REST endpoints for connector management and live data retrieval.

Routes
------
GET    /api/connectors                         — List all registered connectors
GET    /api/connectors/{type}                   — Get connector detail
GET    /api/connectors/{type}/health            — Get connector health
POST   /api/connectors/{type}/connect           — Connect with credentials
POST   /api/connectors/{type}/disconnect        — Disconnect
POST   /api/connectors/{type}/test              — Test connection
POST   /api/connectors/{type}/refresh           — Refresh connector data

Connector-specific data (returns live data from external APIs):
GET    /api/connectors/github/repos                  — List repositories
GET    /api/connectors/github/repos/{owner}/{repo}/branches  — List branches
GET    /api/connectors/github/repos/{owner}/{repo}/pulls     — List pull requests
GET    /api/connectors/github/repos/{owner}/{repo}/workflows — List workflow runs
GET    /api/connectors/jira/projects               — List projects
GET    /api/connectors/jira/issues                 — List recent issues
GET    /api/connectors/slack/channels              — List channels
GET    /api/connectors/teams/teams                 — List teams
GET    /api/connectors/azure-devops/projects       — List projects
GET    /api/connectors/azure-devops/pipelines      — List pipelines
GET    /api/connectors/confluence/spaces           — List spaces
GET    /api/connectors/confluence/pages            — List pages
GET    /api/connectors/servicenow/incidents        — List incidents
GET    /api/connectors/servicenow/change-requests  — List change requests
GET    /api/connectors/notion/databases            — List databases
GET    /api/connectors/notion/pages                — List pages
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.legacy_connectivity_boundary import guard_legacy_connectivity
from backend.auth.dependencies import require_user
from backend.connectors.registry import connector_registry

log = logging.getLogger(__name__)

#: **V1 connectivity strangler boundary (ADR-043).** Every route here either
#: writes a provider credential into a process-wide singleton or makes an
#: authenticated outbound call using one, with no tenant anywhere in the
#: request. ``require_user`` proves who is asking; it does not authorize an
#: external operation, and these predate the path that does.
#:
#: Applied at the router so a route added later inherits it. Disabled by default
#: -- see ``legacy_connectivity_boundary`` for what that breaks and why.
router = APIRouter(
    prefix="/api/connectors",
    tags=["Enterprise Connectors"],
    dependencies=[
        Depends(require_user),
        Depends(guard_legacy_connectivity("/api/connectors/*")),
    ],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CONNECTOR_META: Dict[str, Dict[str, Any]] = {
    "github": {
        "name": "GitHub",
        "description": "Source code management, version control, and CI/CD",
        "authentication_type": "token",
        "auth_fields": [
            {"key": "token", "label": "Personal Access Token", "type": "password", "placeholder": "ghp_..."},
        ],
        "long_description": "Connect to GitHub repositories, manage issues, pull requests, branches, releases, and trigger workflow runs.",
    },
    "jira": {
        "name": "Jira",
        "description": "Issue tracking and agile project management",
        "authentication_type": "basic",
        "auth_fields": [
            {"key": "baseUrl", "label": "Jira Instance URL", "type": "text", "placeholder": "https://your-domain.atlassian.net"},
            {"key": "email", "label": "Email", "type": "text", "placeholder": "user@example.com"},
            {"key": "token", "label": "API Token", "type": "password", "placeholder": "ATATT..."},
        ],
        "long_description": "Connect to Jira Cloud to manage issues, sprints, projects, and workflows.",
    },
    "slack": {
        "name": "Slack",
        "description": "Team communication and collaboration",
        "authentication_type": "token",
        "auth_fields": [
            {"key": "botToken", "label": "Bot Token", "type": "password", "placeholder": "xoxb-..."},
        ],
        "long_description": "Connect to Slack workspaces to send messages, manage channels, and monitor activity.",
    },
    "microsoft-teams": {
        "name": "Microsoft Teams",
        "description": "Team collaboration hub with chat, meetings, and channels",
        "authentication_type": "token",
        "auth_fields": [
            {"key": "accessToken", "label": "Access Token", "type": "password", "placeholder": "eyJ..."},
        ],
        "long_description": "Connect to Microsoft Teams via Graph API for team, channel, and meeting management.",
    },
    "azure-devops": {
        "name": "Azure DevOps",
        "description": "Developer services for planning, coding, and deploying",
        "authentication_type": "basic",
        "auth_fields": [
            {"key": "organization", "label": "Organization", "type": "text", "placeholder": "myorg"},
            {"key": "project", "label": "Project", "type": "text", "placeholder": "myproject"},
            {"key": "pat", "label": "Personal Access Token", "type": "password", "placeholder": "PAT..."},
        ],
        "long_description": "Connect to Azure DevOps to manage work items, pipelines, and repositories.",
    },
    "confluence": {
        "name": "Confluence",
        "description": "Team knowledge base and documentation",
        "authentication_type": "basic",
        "auth_fields": [
            {"key": "siteUrl", "label": "Confluence Site URL", "type": "text", "placeholder": "https://your-domain.atlassian.net/wiki"},
            {"key": "email", "label": "Email", "type": "text", "placeholder": "user@example.com"},
            {"key": "token", "label": "API Token", "type": "password", "placeholder": "ATATT..."},
        ],
        "long_description": "Connect to Confluence to manage spaces, pages, and collaborate on documentation.",
    },
    "servicenow": {
        "name": "ServiceNow",
        "description": "IT service management and operations",
        "authentication_type": "basic",
        "auth_fields": [
            {"key": "instanceUrl", "label": "Instance URL", "type": "text", "placeholder": "https://dev00000.service-now.com"},
            {"key": "username", "label": "Username", "type": "text", "placeholder": "admin"},
            {"key": "password", "label": "Password", "type": "password"},
        ],
        "long_description": "Connect to ServiceNow to manage incidents, change requests, and IT operations.",
    },
    "notion": {
        "name": "Notion",
        "description": "All-in-one workspace for notes, docs, and projects",
        "authentication_type": "token",
        "auth_fields": [
            {"key": "integrationToken", "label": "Integration Token", "type": "password", "placeholder": "secret_..."},
        ],
        "long_description": "Connect to Notion to manage pages, databases, and collaborate on content.",
    },
}

TYPE_ALIASES: Dict[str, str] = {
    "microsoft-teams": "teams",
    "azure-devops": "azure_devops",
}


def _resolve_type(raw: str) -> str:
    return TYPE_ALIASES.get(raw, raw)


def _map_type_alias(backend_type: str) -> str:
    reverse = {v: k for k, v in TYPE_ALIASES.items()}
    return reverse.get(backend_type, backend_type)


# ---------------------------------------------------------------------------
# GET /api/connectors  — List all
# ---------------------------------------------------------------------------


@router.get("")
async def list_connectors() -> Dict[str, Any]:
    types = connector_registry.list_types()
    connectors: List[Dict[str, Any]] = []

    for ctype in types:
        conn = connector_registry.get(ctype)
        if conn is None:
            continue
        try:
            h = _normalize_health(await conn.health())
        except Exception:
            h = {"status": "unavailable"}
        meta = CONNECTOR_META.get(_map_type_alias(ctype), {})
        ops = connector_registry.get_connector_operations(ctype) or {}
        connectors.append({
            "type": _map_type_alias(ctype),
            "name": conn.connector_name,
            "description": meta.get("description", ""),
            "status": h.get("status", "unknown"),
            "health": h,
            "authentication_type": meta.get("authentication_type", "unknown"),
            "capabilities": list(ops.keys()),
            "operations": list(ops.keys()),
            "connection_state": "connected" if h.get("status") in ("available", "healthy") else "disconnected",
            "has_credentials": bool(h.get("authenticated", False)),
            "last_validation": None,
            "latency_ms": h.get("latency_ms"),
            "auth_fields": meta.get("auth_fields", []),
            "long_description": meta.get("long_description", ""),
        })

    # Include connectors that are defined in meta but not yet registered
    existing_types = {_map_type_alias(t) for t in types}
    for cid, meta in CONNECTOR_META.items():
        if cid not in existing_types:
            connectors.append({
                "type": cid,
                "name": meta["name"],
                "description": meta["description"],
                "status": "unavailable",
                "health": {"status": "unavailable", "authenticated": False},
                "authentication_type": meta["authentication_type"],
                "capabilities": [],
                "operations": [],
                "connection_state": "disconnected",
                "has_credentials": False,
                "last_validation": None,
                "latency_ms": None,
                "auth_fields": meta.get("auth_fields", []),
                "long_description": meta.get("long_description", ""),
            })

    return {"connectors": connectors, "total": len(connectors)}


# ---------------------------------------------------------------------------
# GET /api/connectors/{type}  — Detail
# ---------------------------------------------------------------------------


@router.get("/{connector_type}")
async def get_connector_detail(connector_type: str) -> Dict[str, Any]:
    resolved = _resolve_type(connector_type)
    conn = connector_registry.get(resolved)
    meta = CONNECTOR_META.get(connector_type, {})

    if conn is None:
        return {
            "type": connector_type,
            "name": meta.get("name", connector_type),
            "description": meta.get("description", ""),
            "status": "unavailable",
            "health": {"status": "unavailable", "authenticated": False},
            "authentication_type": meta.get("authentication_type", "unknown"),
            "capabilities": [],
            "operations": [],
            "connection_state": "disconnected",
            "has_credentials": False,
            "last_validation": None,
            "latency_ms": None,
            "auth_fields": meta.get("auth_fields", []),
            "long_description": meta.get("long_description", ""),
        }

    try:
        h = _normalize_health(await conn.health())
    except Exception as e:
        h = {"status": "error", "error": str(e)}

    ops = connector_registry.get_connector_operations(resolved) or {}

    return {
        "type": connector_type,
        "name": conn.connector_name,
        "description": meta.get("description", ""),
        "status": h.get("status", "unknown"),
        "health": h,
        "authentication_type": meta.get("authentication_type", "unknown"),
        "capabilities": list(ops.keys()),
        "operations": list(ops.keys()),
        "connection_state": "connected" if h.get("status") in ("available", "healthy") else "disconnected",
        "has_credentials": bool(h.get("authenticated", False)),
        "last_validation": None,
        "latency_ms": h.get("latency_ms"),
        "auth_fields": meta.get("auth_fields", []),
        "long_description": meta.get("long_description", ""),
    }


# ---------------------------------------------------------------------------
# GET /api/connectors/{type}/health  — Health detail
# ---------------------------------------------------------------------------


@router.get("/{connector_type}/health")
async def get_connector_health(connector_type: str) -> Dict[str, Any]:
    resolved = _resolve_type(connector_type)
    conn = connector_registry.get(resolved)

    if conn is None:
        return {
            "status": "unavailable",
            "connector": connector_type,
            "name": CONNECTOR_META.get(connector_type, {}).get("name", connector_type),
            "authenticated": False,
            "authentication_type": CONNECTOR_META.get(connector_type, {}).get("authentication_type", "unknown"),
            "latency_ms": None,
            "version": None,
            "rate_limits": None,
            "last_sync": None,
            "available_operations": [],
            "connection_state": "disconnected",
            "capabilities": [],
        }

    start = time.monotonic()
    try:
        h = _normalize_health(await conn.health())
        latency_ms = int((time.monotonic() - start) * 1000)
    except Exception as e:
        h = {"status": "error", "error": str(e)}
        latency_ms = None

    ops = connector_registry.get_connector_operations(resolved) or {}

    return {
        "status": h.get("status", "unknown"),
        "connector": connector_type,
        "name": conn.connector_name,
        "authenticated": bool(h.get("authenticated", False)),
        "authentication_type": CONNECTOR_META.get(connector_type, {}).get("authentication_type", "unknown"),
        "latency_ms": latency_ms,
        "version": h.get("version"),
        "rate_limits": h.get("rate_limits"),
        "last_sync": h.get("last_sync"),
        "available_operations": list(ops.keys()),
        "connection_state": "connected" if h.get("status") in ("available", "healthy") else "disconnected",
        "capabilities": list(ops.keys()),
    }


# ---------------------------------------------------------------------------
# POST /api/connectors/{type}/connect
# ---------------------------------------------------------------------------


class ConnectRequest(BaseModel):
    credentials: Dict[str, str]


@router.post("/{connector_type}/connect")
async def connect_connector(connector_type: str, body: ConnectRequest) -> Dict[str, Any]:
    resolved = _resolve_type(connector_type)
    conn = connector_registry.get(resolved)

    if conn is None:
        raise HTTPException(status_code=404, detail=f"Connector '{connector_type}' not found")

    start = time.monotonic()
    try:
        conn.configure(body.credentials)
        ok = await conn.initialize()
        latency_ms = int((time.monotonic() - start) * 1000)
        if ok:
            h = _normalize_health(await conn.health())
            return {
                "success": True,
                "status": "connected",
                "health": h,
                "message": f"Successfully connected to {conn.connector_name}",
                "latency_ms": latency_ms,
            }
        else:
            return {
                "success": False,
                "status": "failed",
                "message": f"Failed to connect to {conn.connector_name} — check credentials",
                "latency_ms": latency_ms,
            }
    except Exception as e:
        return {
            "success": False,
            "status": "error",
            "message": str(e),
            "latency_ms": int((time.monotonic() - start) * 1000),
        }


# ---------------------------------------------------------------------------
# POST /api/connectors/{type}/disconnect
# ---------------------------------------------------------------------------


@router.post("/{connector_type}/disconnect")
async def disconnect_connector(connector_type: str) -> Dict[str, Any]:
    resolved = _resolve_type(connector_type)
    conn = connector_registry.get(resolved)

    if conn is None:
        raise HTTPException(status_code=404, detail=f"Connector '{connector_type}' not found")

    try:
        await conn.shutdown()
        return {"success": True, "message": f"{conn.connector_name} disconnected"}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ---------------------------------------------------------------------------
# POST /api/connectors/{type}/test
# ---------------------------------------------------------------------------


@router.post("/{connector_type}/test")
async def test_connector(connector_type: str, body: ConnectRequest) -> Dict[str, Any]:
    resolved = _resolve_type(connector_type)
    conn = connector_registry.get(resolved)

    if conn is None:
        raise HTTPException(status_code=404, detail=f"Connector '{connector_type}' not found")

    start = time.monotonic()
    try:
        conn.configure(body.credentials)
        ok = await conn.initialize()
        latency_ms = int((time.monotonic() - start) * 1000)
        # Clean up after test
        await conn.shutdown()
        return {
            "success": ok,
            "message": "Connection successful" if ok else "Connection failed — check credentials",
            "latency_ms": latency_ms,
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "latency_ms": int((time.monotonic() - start) * 1000),
        }


# ---------------------------------------------------------------------------
# POST /api/connectors/{type}/refresh
# ---------------------------------------------------------------------------


@router.post("/{connector_type}/refresh")
async def refresh_connector(connector_type: str) -> Dict[str, Any]:
    resolved = _resolve_type(connector_type)
    conn = connector_registry.get(resolved)

    if conn is None:
        raise HTTPException(status_code=404, detail=f"Connector '{connector_type}' not found")

    try:
        # Re-initialize to refresh state
        ok = await conn.initialize()
        h = _normalize_health(await conn.health())
        return {"success": ok, "health": h}
    except Exception as e:
        return {"success": False, "health": {"status": "error", "error": str(e)}}


# ===========================================================================
# CONNECTOR-SPECIFIC DATA ENDPOINTS
# ===========================================================================


async def _get_conn_or_404(ctype: str):
    resolved = _resolve_type(ctype)
    conn = connector_registry.get(resolved)
    if conn is None:
        raise HTTPException(status_code=404, detail=f"Connector '{ctype}' not registered. Configure it first via POST /api/connectors/{ctype}/connect")
    return conn


def _normalize_health(h: Dict[str, Any]) -> Dict[str, Any]:
    if h.get("status") == "available":
        h["status"] = "healthy"
    return h


# -----------------------------------------------------------------------
# GitHub
# -----------------------------------------------------------------------


@router.get("/github/repos")
async def github_list_repos(owner: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = await _get_conn_or_404("github")
    return await conn.list_repositories(owner=owner)


@router.get("/github/repos/{owner}/{repo}/branches")
async def github_list_branches(owner: str, repo: str) -> List[Dict[str, Any]]:
    conn = await _get_conn_or_404("github")
    return await conn.list_branches(owner, repo)


@router.get("/github/repos/{owner}/{repo}/pulls")
async def github_list_pull_requests(owner: str, repo: str, state: str = "open") -> List[Dict[str, Any]]:
    conn = await _get_conn_or_404("github")
    return await conn.list_pull_requests(owner, repo, state=state)


@router.get("/github/repos/{owner}/{repo}/workflows")
async def github_list_workflow_runs(owner: str, repo: str, workflow_id: str) -> List[Dict[str, Any]]:
    conn = await _get_conn_or_404("github")
    return await conn.get_workflow_runs(owner, repo, workflow_id)


# -----------------------------------------------------------------------
# Jira
# -----------------------------------------------------------------------


@router.get("/jira/projects")
async def jira_list_projects() -> List[Dict[str, Any]]:
    conn = await _get_conn_or_404("jira")
    return await conn.list_projects()


@router.get("/jira/issues")
async def jira_list_issues(jql: str = "", max_results: int = 20) -> List[Dict[str, Any]]:
    conn = await _get_conn_or_404("jira")
    return await conn.list_issues(jql=jql, max_results=max_results)


# -----------------------------------------------------------------------
# Slack
# -----------------------------------------------------------------------


@router.get("/slack/channels")
async def slack_list_channels(exclude_archived: bool = True) -> List[Dict[str, Any]]:
    conn = await _get_conn_or_404("slack")
    return await conn.list_channels(exclude_archived=exclude_archived)


# -----------------------------------------------------------------------
# Microsoft Teams
# -----------------------------------------------------------------------


@router.get("/teams/teams")
async def teams_list_teams() -> List[Dict[str, Any]]:
    conn = await _get_conn_or_404("teams")
    return await conn.list_teams()


# -----------------------------------------------------------------------
# Azure DevOps
# -----------------------------------------------------------------------


@router.get("/azure-devops/projects")
async def azure_list_projects() -> List[Dict[str, Any]]:
    conn = await _get_conn_or_404("azure_devops")
    return await conn.list_work_items()  # uses list_work_items as proxy for projects


@router.get("/azure-devops/pipelines")
async def azure_list_pipelines() -> List[Dict[str, Any]]:
    conn = await _get_conn_or_404("azure_devops")
    return await conn.list_pipelines()


# -----------------------------------------------------------------------
# Confluence
# -----------------------------------------------------------------------


@router.get("/confluence/spaces")
async def confluence_list_spaces(limit: int = 50) -> List[Dict[str, Any]]:
    conn = await _get_conn_or_404("confluence")
    return await conn.list_spaces(limit=limit)


@router.get("/confluence/pages")
async def confluence_list_pages(space_key: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    conn = await _get_conn_or_404("confluence")
    return await conn.list_pages(space_key=space_key, limit=limit)


# -----------------------------------------------------------------------
# ServiceNow
# -----------------------------------------------------------------------


@router.get("/servicenow/incidents")
async def servicenow_list_incidents(limit: int = 20) -> List[Dict[str, Any]]:
    conn = await _get_conn_or_404("servicenow")
    return await conn.list_incidents(limit=limit)


@router.get("/servicenow/change-requests")
async def servicenow_list_change_requests(limit: int = 20) -> List[Dict[str, Any]]:
    conn = await _get_conn_or_404("servicenow")
    return await conn.list_change_requests(limit=limit)


# -----------------------------------------------------------------------
# Notion
# -----------------------------------------------------------------------


@router.get("/notion/databases")
async def notion_list_databases() -> List[Dict[str, Any]]:
    conn = await _get_conn_or_404("notion")
    return await conn.query_database()  # uses query_database as proxy


@router.get("/notion/pages")
async def notion_list_pages() -> List[Dict[str, Any]]:
    conn = await _get_conn_or_404("notion")
    return await conn.search()  # uses search as proxy for listing pages
