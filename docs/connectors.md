# CortexPrime Connector Reference

## Common Patterns

All connectors share a common architecture built on these base abstractions:

| Pattern | Description |
|---------|-------------|
| **BaseConnector(ABC)** | Abstract base class with `initialize()`, `shutdown()`, `health()`, `configure()`, `get_operations()`, `_execute()` |
| **ConnectorRegistry** | Singleton providing `register()`, `get()`, `list_types()`, `find_connectors_for_operation()`, `find_operations_by_keyword()`, `find_operations_by_tags()`, `find_connectors_by_capability()`, `get_capability_matrix()`, `build_connector_context()` |
| **ConnectorActivityService.record()** | Persists activity to DB, publishes a `CognitionEvent`, and writes an `AuditEntry` |
| **VerificationService.verify_operation()** | Post-write read-back with exponential backoff (max 2 attempts, 1s base delay) |
| **Retry** | `_request()` implements 3-retry exponential backoff (1s, 5s, 30s with jitter). Retryable statuses: `429`, `502`, `503`, `504` |
| **Auth** | All connectors use `httpx.AsyncClient`. Credentials are loaded from environment variables via `CredentialService` |
| **Health** | Each connector exposes a `health()` method backed by an `_available` flag. Connectors degrade gracefully without raising exceptions |

---

## GitHub Connector

| Field | Detail |
|-------|--------|
| **Class** | `GitHubConnector` |
| **Auth** | Bearer PAT |
| **Env Vars** | `GITHUB_TOKEN` |
| **Base URL** | `https://api.github.com` |

### Operations

| Operation | Description |
|-----------|-------------|
| `list_repositories` | List repositories for the authenticated user |
| `get_repository` | Get a single repository by owner/name |
| `create_issue` | Create an issue in a repository |
| `get_issue` | Get a single issue by number |
| `list_issues` | List issues for a repository |
| `update_issue` | Update an existing issue |
| `close_issue` | Close an issue |
| `create_pull_request` | Create a pull request |
| `list_pull_requests` | List pull requests for a repository |
| `get_pull_request` | Get a single pull request by number |
| `list_workflows` | List GitHub Actions workflows |
| `list_commits` | List commits on a branch |
| `list_branches` | List branches in a repository |
| `create_branch` | Create a new branch |

### Verification

Executes `list_repositories` after a write operation and performs a read-back match on repository name and status.

### Retry

Three retries with exponential backoff (1s, 5s, 30s + jitter) on `429`, `502`, `503`, `504`.

### Health

Calls `GET /user` to verify the PAT is valid and the token has not expired.

### Common Failures

| Scenario | Symptom |
|----------|---------|
| Expired or revoked token | `401 Unauthorized` from `/user` |
| Rate limiting | `403 Forbidden` with `X-RateLimit-Remaining: 0` |
| Repository not found | `404 Not Found` -- check owner/name spelling |
| Insufficient PAT scopes | `403` or `404` on specific endpoints (e.g., `repo` scope missing) |

---

## Jira Connector

| Field | Detail |
|-------|--------|
| **Class** | `JiraConnector` |
| **Auth** | Basic (email + API token) |
| **Env Vars** | `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` |
| **Base URL** | `{JIRA_BASE_URL}` |

### Operations

| Operation | Description |
|-----------|-------------|
| `get_issue` | Get a single issue by key |
| `create_issue` | Create a new issue |
| `update_issue` | Update an existing issue |
| `delete_issue` | Delete an issue |
| `list_issues` | List issues with JQL filtering |
| `get_project` | Get a single project by key |
| `list_projects` | List all accessible projects |
| `list_issue_types` | List issue types for a project |
| `add_comment` | Add a comment to an issue |
| `list_comments` | List comments on an issue |
| `list_transitions` | List available transitions for an issue |
| `transition_issue` | Transition an issue to a new status |

### Verification

Creates an issue, then calls `get_issue` by key to confirm the issue was created successfully.

### Retry

Three retries with exponential backoff (1s, 5s, 30s + jitter) on `429`, `502`, `503`, `504`.

### Health

Calls `GET /myself` to verify the credentials are valid and the user has access.

### Common Failures

| Scenario | Symptom |
|----------|---------|
| Invalid or expired API token | `401 Unauthorized` from `/myself` |
| Jira instance unreachable | Connection timeout -- verify `JIRA_BASE_URL` |
| Issue not found | `404 Not Found` -- issue key may be incorrect |
| Insufficient project permissions | `403 Forbidden` on create/update operations |

---

## Slack Connector

| Field | Detail |
|-------|--------|
| **Class** | `SlackConnector` |
| **Auth** | Bot Token |
| **Env Vars** | `SLACK_BOT_TOKEN`, `SLACK_WORKSPACE` |
| **Base URL** | `https://slack.com/api` |

### Operations

| Operation | Description |
|-----------|-------------|
| `send_message` | Send a message to a channel |
| `list_messages` | List messages in a channel |
| `get_channel_history` | Get full history of a channel |
| `create_channel` | Create a new channel |
| `list_channels` | List all channels |
| `join_channel` | Join a channel |
| `add_reaction` | Add a reaction emoji to a message |
| `list_reactions` | List reactions on a message |
| `upload_file` | Upload a file to a channel |
| `list_files` | List files |
| `get_user_info` | Get user profile information |
| `list_users` | List all users in the workspace |

### Verification

Sends a message, then calls `list_messages` to find the sent message by content match.

### Retry

Three retries with exponential backoff (1s, 5s, 30s + jitter) on `429`, `502`, `503`, `504`.

### Health

Calls `GET /api/auth.test` to verify the bot token is valid.

### Common Failures

| Scenario | Symptom |
|----------|---------|
| Invalid or revoked bot token | `401` or `invalid_auth` from `/api/auth.test` |
| Bot not in channel | `not_in_channel` error when sending messages |
| Rate limit exceeded | `429` with `Retry-After` header |
| Channel not found | `channel_not_found` -- verify channel ID is correct |

---

## Teams Connector

| Field | Detail |
|-------|--------|
| **Class** | `TeamsConnector` |
| **Auth** | Bearer via Microsoft Graph |
| **Env Vars** | `TEAMS_TENANT_ID`, `TEAMS_CLIENT_ID`, `TEAMS_CLIENT_SECRET` |
| **Base URL** | `https://graph.microsoft.com/v1.0` |

### Operations

| Operation | Description |
|-----------|-------------|
| `send_message` | Send a message to a Teams channel |
| `list_messages` | List messages in a channel |
| `get_channel` | Get a single channel by ID |
| `list_channels` | List channels in a team |
| `list_teams` | List all teams |
| `get_team` | Get a single team by ID |
| `list_members` | List members of a team or channel |
| `add_member` | Add a member to a team |
| `create_channel` | Create a new channel in a team |
| `send_adaptive_card` | Send an adaptive card to a channel |

### Verification

Sends a message, then calls `list_messages` to find the message by content match.

### Retry

Three retries with exponential backoff (1s, 5s, 30s + jitter) on `429`, `502`, `503`, `504`.

### Health

Calls `GET /v1.0/me` to verify the access token is valid and the Microsoft Graph API is reachable.

### Common Failures

| Scenario | Symptom |
|----------|---------|
| Expired OAuth token | `401 Unauthorized` -- token refresh required |
| Invalid tenant/credentials | `400 InvalidAuthenticationToken` -- verify env vars |
| Resource not found | `404` -- team or channel ID may be incorrect |
| Insufficient Graph permissions | `403 Forbidden` on specific endpoints (e.g., `ChannelMessage.Send` missing) |

---

## Azure DevOps Connector

| Field | Detail |
|-------|--------|
| **Class** | `AzureDevOpsConnector` |
| **Auth** | Basic PAT |
| **Env Vars** | `AZURE_DEVOPS_ORG`, `AZURE_DEVOPS_TOKEN` |
| **Base URL** | `https://dev.azure.com/{AZURE_DEVOPS_ORG}` |

### Operations

| Operation | Description |
|-----------|-------------|
| `get_work_item` | Get a single work item by ID |
| `create_work_item` | Create a new work item |
| `update_work_item` | Update an existing work item |
| `list_work_items` | List work items with WIQL querying |
| `get_repository` | Get a single repository by name or ID |
| `list_repositories` | List repositories in a project |
| `get_pull_request` | Get a single pull request by ID |
| `list_pull_requests` | List pull requests in a repository |
| `create_pull_request` | Create a new pull request |
| `list_builds` | List builds in a pipeline |
| `get_build` | Get a single build by ID |
| `list_releases` | List releases |
| `get_release` | Get a single release by ID |
| `list_pipelines` | List pipelines in a project |
| `run_pipeline` | Trigger a pipeline run |

### Verification

Creates a work item, then calls `get_work_item` by ID to confirm the work item was created.

### Retry

Three retries with exponential backoff (1s, 5s, 30s + jitter) on `429`, `502`, `503`, `504`.

### Health

Calls `GET /{organization}/_apis/projects?api-version=7.0` to verify the PAT and organization are valid.

### Common Failures

| Scenario | Symptom |
|----------|---------|
| Invalid or revoked PAT | `401 Unauthorized` from projects endpoint |
| Organization not found | `404` -- verify `AZURE_DEVOPS_ORG` spelling |
| Rate limiting | `429` with `Retry-After` |
| Insufficient PAT scopes | `403` on specific endpoints (e.g., `vso.code_write` missing for PR creation) |

---

## ServiceNow Connector

| Field | Detail |
|-------|--------|
| **Class** | `ServiceNowConnector` |
| **Auth** | Basic (username + password) |
| **Env Vars** | `SERVICENOW_INSTANCE`, `SERVICENOW_USERNAME`, `SERVICENOW_PASSWORD` |
| **Base URL** | `https://{SERVICENOW_INSTANCE}.service-now.com` |

### Operations

| Operation | Description |
|-----------|-------------|
| `get_incident` | Get a single incident by sys_id |
| `create_incident` | Create a new incident |
| `update_incident` | Update an existing incident |
| `list_incidents` | List incidents with query filters |
| `resolve_incident` | Resolve an incident with a resolution note |
| `get_change_request` | Get a single change request by sys_id |
| `create_change_request` | Create a new change request |
| `update_change_request` | Update an existing change request |
| `list_change_requests` | List change requests |
| `get_catalog_item` | Get a single catalog item by sys_id |
| `list_catalog_items` | List available catalog items |
| `submit_catalog_request` | Submit a request for a catalog item |
| `get_cmdb_ci` | Get a single CMDB CI by sys_id |
| `list_cmdb_cis` | List CMDB CIs with query filters |
| `get_user` | Get a single user by sys_id |
| `list_users` | List users |

### Verification

Creates an incident, then calls `get_incident` by sys_id to confirm creation.

### Retry

Three retries with exponential backoff (1s, 5s, 30s + jitter) on `429`, `502`, `503`, `504`.

### Health

Calls `GET /api/now/table/incident?sysparm_limit=1` to verify the instance is reachable and credentials are valid.

### Common Failures

| Scenario | Symptom |
|----------|---------|
| Invalid credentials | `401 Unauthorized` -- verify username/password |
| Instance unreachable | Connection timeout -- verify `SERVICENOW_INSTANCE` |
| Record not found | `404` -- sys_id may be incorrect |
| Insufficient roles | `403 Forbidden` -- user lacks required roles (e.g., `incident_manager`) |

---

## Confluence Connector

| Field | Detail |
|-------|--------|
| **Class** | `ConfluenceConnector` |
| **Auth** | Basic (email + API token) |
| **Env Vars** | `CONFLUENCE_BASE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN` |
| **Base URL** | `{CONFLUENCE_BASE_URL}` |

### Operations

| Operation | Description |
|-----------|-------------|
| `get_page` | Get a single page by ID |
| `create_page` | Create a new page |
| `update_page` | Update an existing page |
| `delete_page` | Delete a page |
| `list_pages` | List pages in a space |
| `get_space` | Get a single space by key |
| `list_spaces` | List all accessible spaces |
| `get_attachment` | Get a single attachment by ID |
| `list_attachments` | List attachments on a page |
| `upload_attachment` | Upload an attachment to a page |
| `delete_attachment` | Delete an attachment |
| `search_content` | Search content with CQL |
| `get_labels` | Get labels on a page |
| `add_label` | Add a label to a page |
| `get_page_by_title` | Get a page by space key and title |

### Verification

Creates a page, then calls `get_page_by_title` to confirm the page exists with matching title.

### Retry

Three retries with exponential backoff (1s, 5s, 30s + jitter) on `429`, `502`, `503`, `504`.

### Health

Calls `GET /wiki/rest/api/space?limit=1` to verify the instance is reachable and credentials are valid.

### Common Failures

| Scenario | Symptom |
|----------|---------|
| Invalid API token | `401 Unauthorized` from spaces endpoint |
| Base URL misconfigured | Connection failure -- verify `CONFLUENCE_BASE_URL` includes `/wiki` if needed |
| Page not found | `404` -- page ID or title may be incorrect |
| Insufficient permissions | `403 Forbidden` on create/update operations |

---

## Notion Connector

| Field | Detail |
|-------|--------|
| **Class** | `NotionConnector` |
| **Auth** | Bearer (Integration Token) |
| **Env Vars** | `NOTION_TOKEN` |
| **Base URL** | `https://api.notion.com/v1` |

### Operations

| Operation | Description |
|-----------|-------------|
| `get_page` | Get a single page by ID |
| `create_page` | Create a new page (optionally as a child of a parent page or database) |
| `update_page` | Update page properties |
| `get_database` | Get a single database by ID |
| `query_database` | Query a database with filters and sorts |
| `create_database_item` | Create a new item (page) in a database |
| `update_database_item` | Update an existing database item |
| `list_users` | List all users in the workspace |
| `get_block_children` | Get block children of a page or block |
| `append_block_children` | Append new blocks as children of a block |
| `create_comment` | Create a comment on a page |
| `list_comments` | List comments on a page |

### Verification

Creates a page, then calls `get_page` by ID to confirm the page exists.

### Retry

Three retries with exponential backoff (1s, 5s, 30s + jitter) on `429`, `502`, `503`, `504`.

### Health

Calls `GET /v1/users/me` to verify the integration token is valid.

### Common Failures

| Scenario | Symptom |
|----------|---------|
| Invalid or revoked token | `401 Unauthorized` from `/v1/users/me` |
| Page not found or no access | `404 Object not found` -- verify the integration is shared with the page |
| Rate limiting | `429 Too Many Requests` |
| Missing integration capabilities | `403` -- ensure integration has the correct capabilities granted in Notion |
