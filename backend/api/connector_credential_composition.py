"""The one place V1 connector credentials may come from the environment.

Phase 5.15, ADR-058. Before this module, every V1 connector read its own
provider credential straight out of the process environment at
``initialize()`` time — ``self._token = self._token or os.getenv("GITHUB_TOKEN")``
— and ``CredentialService.load`` fell back to the environment on its own. The
consequence was demonstrated in Phase 5.14: merely *booting* the application
consumed whatever credentials ``.env`` happened to hold and contacted the real
providers, because nobody had decided anything.

Ambient credentials are now a composition decision:

* Connector modules read **nothing** from the environment. Their credentials
  arrive through ``BaseConnector.configure()`` / ``CredentialService`` — a
  store somebody explicitly populated.
* ``CredentialService`` has **no environment fallback** any more. Empty store,
  empty answer, degraded connector — visibly.
* This module is the single, deliberate act that carries environment
  configuration into that store, called once from the application lifespan
  (``backend/main.py``) before connectors initialize. A process that never
  calls it — a harness, a test, the governed runtime, an importer — consumes
  no provider credential no matter what the environment contains.

Deliberately NOT covered here: ``DOCKER_HOST``/``DOCKER_TLS_VERIFY``/
``DOCKER_CERT_PATH`` and ``KUBECONFIG`` (local infrastructure endpoints the
respective SDKs define, not provider credentials) and the platform's own
bootstrap secret ``VAULT_TOKEN`` (part of the bootstrap trust model, ADR-040,
read by the production connectivity builder).

The fitness rule ``BND-AMBIENT-CREDENTIALS`` holds the boundary: provider
credential environment reads outside this module (and the other allowlisted
composition/bootstrap sites) are violations.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Iterable, Mapping, Optional

__all__ = [
    "CONNECTOR_ENVIRONMENT",
    "read_connector_environment",
    "bootstrap_connector_credentials",
]

log = logging.getLogger(__name__)

#: connector_type -> {credential key (as ``configure()`` expects it): env var}.
#: The env var names are the ones the connectors themselves historically read,
#: so a deployment's existing configuration keeps working unchanged — what
#: moved is WHERE the read happens, not WHAT is read.
CONNECTOR_ENVIRONMENT: Mapping[str, Mapping[str, str]] = {
    "github": {"token": "GITHUB_TOKEN"},
    "jira": {"baseUrl": "JIRA_BASE_URL", "email": "JIRA_EMAIL",
             "token": "JIRA_API_TOKEN"},
    "slack": {"botToken": "SLACK_BOT_TOKEN"},
    "teams": {"accessToken": "TEAMS_ACCESS_TOKEN"},
    "circleci": {"token": "CIRCLECI_TOKEN"},
    "notion": {"integrationToken": "NOTION_API_KEY",
               "notionVersion": "NOTION_VERSION"},
    "confluence": {"siteUrl": "CONFLUENCE_BASE_URL",
                   "email": "CONFLUENCE_EMAIL",
                   "token": "CONFLUENCE_API_TOKEN"},
    "azure_devops": {"organization": "AZURE_DEVOPS_ORG",
                     "project": "AZURE_DEVOPS_PROJECT",
                     "pat": "AZURE_DEVOPS_PAT"},
    "gitlab_ci": {"url": "GITLAB_URL", "token": "GITLAB_TOKEN"},
    "jenkins": {"url": "JENKINS_URL", "user": "JENKINS_USER",
                "pass": "JENKINS_PASS"},
    "servicenow": {"instanceUrl": "SERVICENOW_INSTANCE",
                   "username": "SERVICENOW_USERNAME",
                   "password": "SERVICENOW_PASSWORD"},
}


def read_connector_environment(connector_type: str) -> dict:
    """Read one connector's configuration from the environment. Values only
    travel to the credential store; they are never logged and never returned
    to a caller that would put them anywhere else."""
    mapping = CONNECTOR_ENVIRONMENT.get(connector_type, {})
    found = {}
    for key, variable in mapping.items():
        value = os.getenv(variable, "")
        if value:
            found[key] = value
    return found


def bootstrap_connector_credentials(
    connector_types: Optional[Iterable[str]] = None,
) -> dict:
    """The composition act: environment → credential store, once, visibly.

    Returns ``{connector_type: bool}`` — which connectors received any
    configuration — so the caller can log a truthful summary without a single
    credential value appearing anywhere.
    """
    from backend.services.credential_service import CredentialService

    outcome: dict = {}
    for connector_type in (connector_types or CONNECTOR_ENVIRONMENT):
        credentials = read_connector_environment(connector_type)
        if credentials:
            CredentialService.store(connector_type, credentials)
        outcome[connector_type] = bool(credentials)
    configured = sorted(t for t, present in outcome.items() if present)
    log.info(
        "connector credential bootstrap: %d/%d connector types configured "
        "from the environment (%s)",
        len(configured), len(outcome), ", ".join(configured) or "none")
    return outcome
