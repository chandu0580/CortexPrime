import logging
import os
from typing import Dict

log = logging.getLogger(__name__)

# Keep in-memory store
_CREDENTIAL_STORE: Dict[str, dict] = {}

class CredentialService:
    @classmethod
    def store(cls, connector_type: str, credentials: dict) -> None:
        """Stores credentials for a connector type."""
        log.info(f"Storing credentials for {connector_type}")
        _CREDENTIAL_STORE[connector_type] = dict(credentials)

    @classmethod
    def load(cls, connector_type: str) -> dict:
        """Loads credentials, falling back to environment variables if not stored."""
        if connector_type in _CREDENTIAL_STORE:
            return dict(_CREDENTIAL_STORE[connector_type])

        # Fallback to environment variables
        return cls._load_from_env(connector_type)

    @classmethod
    def exists(cls, connector_type: str) -> bool:
        """Checks if credentials exist in the store or environment."""
        if connector_type in _CREDENTIAL_STORE:
            return True
        # Check if environment variables are populated
        creds = cls._load_from_env(connector_type)
        return any(creds.values())

    @classmethod
    def remove(cls, connector_type: str) -> None:
        """Removes credentials from the store."""
        if connector_type in _CREDENTIAL_STORE:
            del _CREDENTIAL_STORE[connector_type]

    @classmethod
    def _load_from_env(cls, connector_type: str) -> dict:
        """Helper to map connector type to environment variables."""
        if connector_type == "github":
            return {"token": os.getenv("GITHUB_TOKEN", "")}
        elif connector_type == "jira":
            return {
                "baseUrl": os.getenv("JIRA_BASE_URL", ""),
                "email": os.getenv("JIRA_EMAIL", ""),
                "token": os.getenv("JIRA_API_TOKEN", "")
            }
        elif connector_type == "slack":
            return {"botToken": os.getenv("SLACK_BOT_TOKEN", "")}
        elif connector_type == "teams":
            return {"accessToken": os.getenv("TEAMS_ACCESS_TOKEN", "")}
        elif connector_type == "azure_devops":
            return {
                "organization": os.getenv("AZURE_DEVOPS_ORG", ""),
                "project": os.getenv("AZURE_DEVOPS_PROJECT", ""),
                "pat": os.getenv("AZURE_DEVOPS_PAT", "")
            }
        elif connector_type == "servicenow":
            return {
                "instanceUrl": os.getenv("SERVICENOW_INSTANCE", ""),
                "username": os.getenv("SERVICENOW_USERNAME", ""),
                "password": os.getenv("SERVICENOW_PASSWORD", "")
            }
        elif connector_type == "confluence":
            return {
                "siteUrl": os.getenv("CONFLUENCE_BASE_URL", ""),
                "email": os.getenv("CONFLUENCE_EMAIL", ""),
                "token": os.getenv("CONFLUENCE_API_TOKEN", "")
            }
        elif connector_type == "notion":
            return {
                "integrationToken": os.getenv("NOTION_API_KEY", ""),
                "notionVersion": os.getenv("NOTION_VERSION", "")
            }
        return {}
