from backend.connector.adapters.docker import DockerAdapter
from backend.connector.adapters.github import GitHubAdapter
from backend.connector.adapters.grafana import GrafanaAdapter
from backend.connector.adapters.jira import JiraAdapter
from backend.connector.adapters.kubernetes import KubernetesAdapter
from backend.connector.adapters.prometheus import PrometheusAdapter
from backend.connector.adapters.slack import SlackAdapter

ADAPTER_CLASSES = [
    GitHubAdapter,
    JiraAdapter,
    SlackAdapter,
    KubernetesAdapter,
    DockerAdapter,
    PrometheusAdapter,
    GrafanaAdapter,
]

__all__ = [
    "GitHubAdapter",
    "JiraAdapter",
    "SlackAdapter",
    "KubernetesAdapter",
    "DockerAdapter",
    "PrometheusAdapter",
    "GrafanaAdapter",
    "ADAPTER_CLASSES",
]
