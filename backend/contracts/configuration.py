"""Configuration vocabulary.

Owner: Administration capability (declared), BC-6 Governance (consumed).

Constitution S8 requires that resource criticality be "a declared property of a
resource, sourced from tenant configuration" rather than inferred. This module
is that declaration.

It exists to make a specific defect impossible. The current implementation
classifies criticality by substring-matching container names, so a resource
named ``prod-payments-api`` classifies as low risk (compliance report V7).
``ResourceDeclaration`` replaces guessing with stating.

Configuration here is *declarative data only*: what a tenant has asserted about
its estate. Runtime settings, feature flags, and connection details are
platform concerns and deliberately absent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contracts.policy import RiskLevel
from backend.contracts.tenant import TenantScope

__all__ = [
    "ConfigurationSource",
    "ResourceDeclaration",
    "EnvironmentDeclaration",
    "DeclarationSet",
]


class ConfigurationSource(str, Enum):
    """Where a declaration came from.

    Provenance matters for trust: an operator's explicit statement outranks an
    import, which outranks a platform default. Recording the source lets
    Governance apply that ordering rather than treating all declarations as
    equally authoritative.
    """

    OPERATOR = "operator"
    """Stated explicitly by a human operator. Highest authority."""

    IMPORTED = "imported"
    """Derived from an external system of record (CMDB, tags, IaC)."""

    PLATFORM_DEFAULT = "platform_default"
    """Applied by CortexPrime in the absence of any statement. Lowest authority."""

    @property
    def authority_rank(self) -> int:
        return _SOURCE_RANK[self]


_SOURCE_RANK = {
    ConfigurationSource.PLATFORM_DEFAULT: 0,
    ConfigurationSource.IMPORTED: 1,
    ConfigurationSource.OPERATOR: 2,
}


@dataclass(frozen=True)
class ResourceDeclaration(Contract):
    """A tenant's assertion about one resource.

    ``criticality`` is mandatory. This class exists precisely so that
    criticality is stated; permitting it to be omitted would reintroduce the
    guessing this module is meant to eliminate.
    """

    CONTRACT_NAME = "cortexprime.configuration.resource"

    system: str
    resource_id: str
    criticality: RiskLevel
    source: ConfigurationSource
    owner: Optional[str] = None
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        for label, value in (("system", self.system), ("resource_id", self.resource_id)):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be a non-blank string")
        if not isinstance(self.criticality, RiskLevel):
            raise ContractViolation("criticality must be a RiskLevel")
        if not isinstance(self.source, ConfigurationSource):
            raise ContractViolation("source must be a ConfigurationSource")

    @property
    def key(self) -> tuple[str, str]:
        """Stable lookup key: a resource is identified by system and id."""
        return (self.system, self.resource_id)


@dataclass(frozen=True)
class EnvironmentDeclaration(Contract):
    """A tenant's assertion about one environment.

    ``is_production`` is separate from ``baseline_criticality`` because they
    answer different questions: whether real users are affected, and how severe
    an undeclared resource in this environment should be assumed to be.
    """

    CONTRACT_NAME = "cortexprime.configuration.environment"

    environment: str
    is_production: bool
    baseline_criticality: RiskLevel
    source: ConfigurationSource

    def __post_init__(self) -> None:
        if not isinstance(self.environment, str) or not self.environment.strip():
            raise ContractViolation("environment must be a non-blank string")
        if not isinstance(self.baseline_criticality, RiskLevel):
            raise ContractViolation("baseline_criticality must be a RiskLevel")
        if self.is_production and self.baseline_criticality < RiskLevel.MEDIUM:
            raise ContractViolation(
                "a production environment cannot declare a baseline criticality below "
                "medium; fail closed on the environment that matters"
            )


@dataclass(frozen=True)
class DeclarationSet(Contract):
    """Everything a tenant has declared about its estate.

    Lookup is deliberately *not* fuzzy. ``criticality_for`` returns ``None``
    when a resource has no declaration, and Governance fails closed on that
    absence. Returning a default here would silently recreate the guessing this
    module eliminates.
    """

    CONTRACT_NAME = "cortexprime.configuration.declarations"

    scope: TenantScope
    version: str
    resources: tuple[ResourceDeclaration, ...] = field(default_factory=tuple)
    environments: tuple[EnvironmentDeclaration, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version.strip():
            raise ContractViolation("version must identify this declaration set")
        if not isinstance(self.resources, tuple) or not isinstance(self.environments, tuple):
            raise ContractViolation("declaration collections must be tuples")

        resource_keys = [declaration.key for declaration in self.resources]
        if len(set(resource_keys)) != len(resource_keys):
            raise ContractViolation("resources must not contain duplicate (system, resource_id)")

        environment_names = [declaration.environment for declaration in self.environments]
        if len(set(environment_names)) != len(environment_names):
            raise ContractViolation("environments must not contain duplicates")

    def criticality_for(self, system: str, resource_id: str) -> Optional[RiskLevel]:
        """Return the declared criticality, or ``None`` if undeclared.

        ``None`` means "nobody has said" -- it does not mean "low".
        """
        for declaration in self.resources:
            if declaration.key == (system, resource_id):
                return declaration.criticality
        return None

    def environment_for(self, environment: str) -> Optional[EnvironmentDeclaration]:
        for declaration in self.environments:
            if declaration.environment == environment:
                return declaration
        return None
