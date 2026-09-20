# GitHub connector — operator runbook

Connect CortexPrime to named GitHub repositories, read what changed, and let it
post one governed comment. Architecture: `docs/CONNECTOR_ARCHITECTURE.md`.
Decision record: `docs/adr/ADR-126-phase-11-2-github-connector.md`.

## What you need before connecting

| Prerequisite | Why |
|---|---|
| A **GitHub App**, installed on the repositories you want connected | the production credential: short-lived, repository-scoped installation tokens |
| Its **App id** and **private key (PEM)** stored in Vault KV | the key never appears in an environment variable, a ConfigMap, an image or a log |
| The **installation id** of that installation | an installation is what a token is minted against |
| A running CortexPrime release (the `cortexprime-governed` chart) | GitHub is a connection on an existing deployment, not a separate deployment |

**Permissions to grant the App** (read-only except the last, and nothing else):

| Permission | Needed for |
|---|---|
| Metadata: Read | `get_repository` |
| Contents: Read | `list_commits`, `get_commit` |
| Pull requests: Read | `list_pull_requests`, `get_pull_request` |
| Actions: Read | `list_workflow_runs`, `get_workflow_run` |
| Deployments: Read | `list_deployments` |
| Issues: **Read and write** | `get_issue`, and the one write: `create_issue_comment` |

CortexPrime asks GitHub to mint each token with exactly these permissions and
only the connected repositories, so a token it holds can do no more than the
capabilities it ships — even if the App itself were granted more.

## Connect (one Vault step, then chart values)

1. **Store the credential** (the operator does this; CortexPrime never writes it):

   ```sh
   # production: the GitHub App's own identity
   vault kv put secret/cortexprime/github/app app_id=<APP_ID> private_key=@app-key.pem

   # development/staging only: a token instead of an App
   vault kv put secret/cortexprime/providers/<tenant>/<env>/github token=-
   vault kv put secret/cortexprime/providers/<tenant>/<env>/github-contained token=-
   ```

   `token=-` makes the Vault CLI read the value from stdin, so the credential
   never reaches a shell history or a process list.

2. **Let the runtime read it** (idempotent; grants read on those paths only):

   ```sh
   TENANT=<tenant id> ENVIRONMENT=production \
   VAULT_ADDR=https://vault.example:8200 VAULT_TOKEN=<admin> \
     sh scripts/connector/configure_vault_github.sh
   ```

3. **Turn the connection on:**

   ```sh
   helm upgrade --install cortexprime ./helm/cortexprime-governed -n cortexprime \
     --set github.enabled=true \
     --set-string github.repositories="owner/repo-a,owner/repo-b" \
     --set github.app.installationId=<INSTALLATION_ID> \
     --set-string github.worker.digest=$(sha256sum workers/contained_github_comment/worker.py | cut -d' ' -f1) \
     --wait
   ```

4. **Check it:** `GET /api/v1/connectors/github` with a token for the
   connection's tenant. `CONNECTED` means every connected repository was read
   with this connection's own credential, just now.

`github.credentials=vault-token` switches to the stored-token path; production
**refuses** it, because a personal access token is long-lived and account-wide.

## Reading health

| State | Meaning | What to do |
|---|---|---|
| CONNECTED | every connected repository is readable | nothing |
| DEGRADED | reads work; the comment capability is unavailable (its worker is down or not deployed) | `kubectl -n <ns> get deploy contained-github-worker` |
| PERMISSION_DENIED | the credential authenticates and GitHub refused the permission | grant the permission above that the check names, then re-install the App |
| AUTHENTICATION_REQUIRED | the credential was refused or could not be obtained from Vault | check the Vault path and policy; the check names which |
| MISCONFIGURED | a connected repository is not visible to this credential, or a capability contract conflicts | GitHub answers 404 for "does not exist" *and* for "you may not see it"; install the App on that repository |
| RATE_LIMITED | GitHub's primary or secondary limit refused a call | wait for the reset; the error class distinguishes the two |
| UNAVAILABLE | GitHub could not be reached | check egress |
| DISABLED | your tenant has no GitHub connection | connect one for your tenant |

## Common failures and their fixes

| Symptom | Cause | Fix |
|---|---|---|
| `AUTHENTICATION_REQUIRED` right after a Vault policy change | the runtime held a Vault login minted before the change | it now retries once with a fresh login; if it persists, the policy does not cover the path the check names |
| `owner/repo '…' is outside this tenant's github connection` | the capability targeted a repository the connection does not name | add it to `github.repositories` deliberately, or use the right repository |
| `repository_out_of_scope` from the worker | the worker's compiled binding does not include that repository | the worker is bound at deploy time; `helm upgrade` rebinds it |
| The comment capability is `unavailable` | no worker is deployed for this connection | `github.worker.enabled=true` and a pinned digest |
| A write is refused with `approval_required` | every GitHub write faces a human; none is delegated to autonomy | approve it in the queue |

## What it can and cannot do

- **Reads:** repository, commits (list and detail), pull requests (list and
  detail), workflow runs (list and detail), deployments, one issue thread.
  Responses are normalized: author, timestamps, subject line, files changed,
  additions and deletions, branch, head sha, conclusion — bounded, never a raw
  GitHub payload.
- **Writes:** exactly one — a comment on an existing issue or pull request, in
  a connected repository, after a human approval, executed by a contained
  worker that holds no standing credential, attributed in the comment body to
  the action that produced it, and read back independently before it counts.
- **Cannot:** open issues, merge, push, dispatch workflows, change settings,
  read files or search code. None of those is a capability, so none can be
  asked for.
- **Repository content is data.** A commit message or an issue body that
  contains instructions is evidence, not authority; nothing a repository
  contains can reach a capability.

## Limits (stated, not implied)

- One GitHub connection per deployment.
- No webhook ingestion in this phase (deliberately deferred; an unsigned
  ingestion path is worse than none).
- A governed capability is executed by the process holding the scheduler role.
  A second replica, or any caller outside that process, can start an execution
  that nothing will dispatch (ADR-126 F-3).
- The rate limiter is per process.
- Numeric identifiers (`pull_number`, `workflow_run_id`, `issue_number`) are
  passed as text: a path parameter must be a resource segment, which is what
  keeps `../` out of a URL.
