"""
Comprehensive validation tests for Enterprise Architecture Intelligence (AI CTO).
Verifies all 10 parts plus the Hospital Management System validation scenario.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from backend.services.enterprise_architecture_intelligence import (
    EnterpriseArchitectureIntelligence,
    RequirementIntelligence,
    DomainIntelligence,
    ArchitectureIntelligence,
    TechnologyDecisionEngine,
    DatabaseDesigner,
    ApiIntelligence,
    EventArchitecture,
    EngineeringPlanner,
    ArchitectureGraphIntegration,
    ARCHITECTURE_EVENTS,
)
from backend.events.enterprise_event_types import EnterpriseEventTypes as EET


# =============================================================================
# Hospital Management System — validation input
# =============================================================================

HOSPITAL_INPUT = """
Build an Enterprise Hospital Management System.

The system should manage patient registration, appointment scheduling,
electronic medical records, pharmacy management, laboratory tests,
billing and insurance claims processing.

Requirements:
- Patient check-in and registration with demographics
- Doctor appointment booking and calendar management
- Electronic health records with secure access
- Prescription management and pharmacy integration
- Lab test ordering and results management
- Billing, invoicing, and insurance claim processing
- Reporting and analytics dashboard
- HIPAA compliance for data privacy
- Role-based access control for doctors, nurses, admins
- Integration with existing EHR systems
"""


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def ai():
    arch = EnterpriseArchitectureIntelligence()
    arch._projects = {}
    arch._analyses = {}
    return arch


# =============================================================================
# Pipeline Constants
# =============================================================================

class TestArchitectureConstants:
    def test_all_events_defined(self):
        assert len(ARCHITECTURE_EVENTS) == 11

    def test_events_in_enterprise_types(self):
        arch_events = {a for a in dir(EET) if a.startswith("ARCHITECTURE_")}
        for key, val in ARCHITECTURE_EVENTS.items():
            # Find the EET attribute matching this value
            found = False
            for attr in arch_events:
                if getattr(EET, attr) == val:
                    found = True
                    break
            assert found, f"{key}: {val} not in EET"

    def test_event_strings(self):
        assert EET.ARCHITECTURE_ANALYSIS_STARTED == "architecture.analysis_started"
        assert EET.ARCHITECTURE_ANALYSIS_COMPLETED == "architecture.analysis_completed"
        assert EET.ARCHITECTURE_DOMAIN_GENERATED == "architecture.domain_generated"
        assert EET.ARCHITECTURE_MISSIONS_GENERATED == "architecture.missions_generated"
        assert EET.ARCHITECTURE_DECISION_RECORDED == "architecture.decision_recorded"

    def test_event_hub_routing(self):
        from backend.services.enterprise_event_hub import _topic_for_event
        assert _topic_for_event("architecture.analysis_started") == "enterprise:architecture"
        assert _topic_for_event("architecture.missions_generated") == "enterprise:architecture"


# =============================================================================
# Part 1 — Requirement Intelligence
# =============================================================================

class TestRequirementIntelligence:
    def test_analyze_hospital(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        assert reqs["industry"] == "healthcare"
        assert len(reqs["functional_requirements"]) > 0
        assert any("patient" in r.lower() for r in reqs["functional_requirements"])
        assert any("appointment" in r.lower() for r in reqs["functional_requirements"])
        assert "Patient" in reqs["actors"]
        assert "Doctor" in reqs["actors"]
        assert "Nurse" in reqs["actors"]
        assert len(reqs["non_functional_requirements"]) > 0
        assert len(reqs["security_requirements"]) > 0

    def test_analyze_finance(self):
        reqs = RequirementIntelligence.analyze("Build a banking system with accounts, transactions, and loans.")
        assert reqs["industry"] == "finance"
        assert "Customer" in reqs["actors"]

    def test_analyze_ecommerce(self):
        reqs = RequirementIntelligence.analyze("Build an online store with products, cart, and orders.")
        assert reqs["industry"] == "ecommerce"

    def test_empty_input(self):
        reqs = RequirementIntelligence.analyze("")
        assert reqs["industry"] == "saas"
        assert len(reqs["functional_requirements"]) > 0

    def test_requirements_structure(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        assert "functional_requirements" in reqs
        assert "non_functional_requirements" in reqs
        assert "actors" in reqs
        assert "constraints" in reqs
        assert "risks" in reqs
        assert "security_requirements" in reqs
        assert "compliance_requirements" in reqs


# =============================================================================
# Part 2 — Domain Intelligence
# =============================================================================

class TestDomainIntelligence:
    def test_generate_hospital_domain(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        assert domain["industry"] == "healthcare"
        assert len(domain["entities"]) > 0
        assert len(domain["bounded_contexts"]) > 0
        assert len(domain["capabilities"]) > 0
        entity_names = [e["name"] for e in domain["entities"]]
        assert "Patient" in entity_names
        assert "Doctor" in entity_names
        assert "Appointment" in entity_names

    def test_domain_entities_have_attributes(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        for entity in domain["entities"]:
            assert len(entity["attributes"]) > 0
            assert entity["key"]

    def test_domain_relationships(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        assert len(domain["relationships"]) > 0
        for rel in domain["relationships"]:
            assert "from_entity" in rel
            assert "to_entity" in rel
            assert "type" in rel

    def test_domain_capabilities_have_priority(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        for cap in domain["capabilities"]:
            assert cap["priority"] in ("high", "medium", "low")


# =============================================================================
# Part 3 — Architecture Intelligence
# =============================================================================

class TestArchitectureIntelligence:
    def test_generate_hospital_architecture(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        arch = ArchitectureIntelligence.generate(reqs, domain)
        assert arch["pattern"] == "Microservices"
        assert len(arch["services"]) > 0
        service_names = [s["name"] for s in arch["services"]]
        assert any("Service" in s for s in service_names)

    def test_services_have_responsibilities(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        arch = ArchitectureIntelligence.generate(reqs, domain)
        for svc in arch["services"]:
            assert len(svc["responsibilities"]) > 0
            assert svc["language"] == "Python"

    def test_architecture_has_gateway(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        arch = ArchitectureIntelligence.generate(reqs, domain)
        assert arch["api_gateway"]["type"] == "API Gateway"

    def test_architecture_has_auth(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        arch = ArchitectureIntelligence.generate(reqs, domain)
        assert arch["auth_flow"]["protocol"] == "OAuth 2.0 + OpenID Connect"

    def test_architecture_has_monitoring(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        arch = ArchitectureIntelligence.generate(reqs, domain)
        assert arch["monitoring_architecture"]["metrics"] == "Prometheus + Grafana"


# =============================================================================
# Part 4 — Technology Decision Engine
# =============================================================================

class TestTechnologyDecisionEngine:
    def test_recommend_hospital_tech(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        tech = TechnologyDecisionEngine.recommend(reqs)
        assert len(tech["decisions"]) > 0
        assert tech["industry"] == "healthcare"
        layers = [d["layer"] for d in tech["decisions"]]
        assert "Backend" in layers
        assert "Frontend" in layers
        assert "Database" in layers

    def test_tech_decisions_have_reasoning(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        tech = TechnologyDecisionEngine.recommend(reqs)
        for cat in tech["decisions"]:
            for choice in cat["choices"]:
                assert choice["reason"]
                assert choice["alternatives"]
                assert choice["risk"] in ("low", "medium", "high")

    def test_healthcare_includes_fhir(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        tech = TechnologyDecisionEngine.recommend(reqs)
        layers = [d["layer"] for d in tech["decisions"]]
        assert "Health Data Exchange" in layers

    def test_finance_tech(self):
        reqs = RequirementIntelligence.analyze("Build a banking platform")
        tech = TechnologyDecisionEngine.recommend(reqs)
        assert tech["industry"] == "finance"


# =============================================================================
# Part 5 — Database Designer
# =============================================================================

class TestDatabaseDesigner:
    def test_design_hospital_db(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        db = DatabaseDesigner.design(domain)
        assert len(db["tables"]) > 0
        table_names = [t["table_name"] for t in db["tables"]]
        assert any("patient" in t.lower() for t in table_names)

    def test_tables_have_columns(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        db = DatabaseDesigner.design(domain)
        for table in db["tables"]:
            assert len(table["columns"]) > 0

    def test_tables_have_indexes(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        db = DatabaseDesigner.design(domain)
        for table in db["tables"]:
            assert len(table["indexes"]) > 0

    def test_migration_strategy(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        db = DatabaseDesigner.design(domain)
        assert db["migration_strategy"]["tool"] == "Alembic"

    def test_er_model(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        db = DatabaseDesigner.design(domain)
        assert len(db["er_model"]["entities"]) > 0
        assert len(db["er_model"]["relationships"]) > 0


# =============================================================================
# Part 6 — API Intelligence
# =============================================================================

class TestApiIntelligence:
    def test_generate_hospital_apis(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        arch = ArchitectureIntelligence.generate(reqs, domain)
        apis = ApiIntelligence.generate(arch, domain)
        assert apis["total_endpoints"] > 0
        assert len(apis["apis"]) > 0

    def test_apis_have_crud_patterns(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        arch = ArchitectureIntelligence.generate(reqs, domain)
        apis = ApiIntelligence.generate(arch, domain)
        methods = {a["method"] for a in apis["apis"]}
        assert "GET" in methods
        assert "POST" in methods
        assert "PATCH" in methods
        assert "DELETE" in methods

    def test_apis_have_auth_requirement(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        arch = ArchitectureIntelligence.generate(reqs, domain)
        apis = ApiIntelligence.generate(arch, domain)
        for api in apis["apis"]:
            assert api["auth"] in ("required", "admin")

    def test_api_versioning(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        arch = ArchitectureIntelligence.generate(reqs, domain)
        apis = ApiIntelligence.generate(arch, domain)
        assert apis["versioning"]["current_version"] == "v1"

    def test_rate_limiting(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        arch = ArchitectureIntelligence.generate(reqs, domain)
        apis = ApiIntelligence.generate(arch, domain)
        assert apis["rate_limiting"]["default"]


# =============================================================================
# Part 7 — Event Architecture
# =============================================================================

class TestEventArchitecture:
    def test_generate_hospital_events(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        evts = EventArchitecture.generate(domain)
        assert evts["total_events"] > 0
        assert len(evts["domain_events"]) > 0

    def test_event_structure(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        evts = EventArchitecture.generate(domain)
        for e in evts["domain_events"]:
            assert e["event"]
            assert e["type"] == "domain_event"
            assert e["schema"]

    def test_queue_recommendations(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        evts = EventArchitecture.generate(domain)
        q = evts["queue_recommendations"]
        assert q["technology"] == "RabbitMQ"
        assert q["retry_strategy"]
        assert q["dead_letter_queue"]


# =============================================================================
# Part 8 — Engineering Planner
# =============================================================================

class TestEngineeringPlanner:
    def test_generate_hospital_plan(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        arch = ArchitectureIntelligence.generate(reqs, domain)
        plan = EngineeringPlanner.generate(reqs, domain, arch)
        assert plan["total_epics"] > 0
        assert plan["total_features"] > 0
        assert plan["total_stories"] > 0

    def test_epics_have_features(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        arch = ArchitectureIntelligence.generate(reqs, domain)
        plan = EngineeringPlanner.generate(reqs, domain, arch)
        for epic in plan["epics"]:
            assert len(epic["features"]) > 0
            assert len(epic["stories"]) > 0

    def test_epics_have_effort(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        arch = ArchitectureIntelligence.generate(reqs, domain)
        plan = EngineeringPlanner.generate(reqs, domain, arch)
        for epic in plan["epics"]:
            assert epic["estimated_effort"]
            assert epic["risk_score"]

    def test_missions_generated(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        arch = ArchitectureIntelligence.generate(reqs, domain)
        plan = EngineeringPlanner.generate(reqs, domain, arch)
        assert len(plan["missions"]) > 0
        for m in plan["missions"]:
            assert m["mission_id"].startswith("mission-")
            assert m["objective"]
            assert m["status"] == "planned"


# =============================================================================
# Part 10 — Full Orchestrator
# =============================================================================

class TestEnterpriseArchitectureIntelligence:
    @pytest.mark.asyncio
    async def test_create_project(self, ai):
        proj = await ai.create_project(
            name="Test Project",
            description="A test project",
            input_text=HOSPITAL_INPUT,
        )
        assert proj["project_id"].startswith("arch-")
        assert proj["status"] == "created"
        assert proj["name"] == "Test Project"

    @pytest.mark.asyncio
    async def test_get_project(self, ai):
        created = await ai.create_project(name="Get Test")
        fetched = await ai.get_project(created["project_id"])
        assert fetched is not None
        assert fetched["project_id"] == created["project_id"]

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, ai):
        assert await ai.get_project("nonexistent") is None

    @pytest.mark.asyncio
    async def test_list_projects(self, ai):
        await ai.create_project(name="A")
        await ai.create_project(name="B")
        assert len(await ai.list_projects()) == 2

    @pytest.mark.asyncio
    async def test_delete_project(self, ai):
        p = await ai.create_project(name="Del")
        assert await ai.delete_project(p["project_id"])
        assert await ai.get_project(p["project_id"]) is None

    @pytest.mark.asyncio
    async def test_delete_not_found(self, ai):
        assert not await ai.delete_project("nonexistent")


# =============================================================================
# Full Hospital Management Validation Scenario
# =============================================================================

class TestHospitalManagementScenario:
    """Validates the Hospital Management System end-to-end scenario."""

    @pytest.mark.asyncio
    async def test_requirements_extracted(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        assert len(reqs["functional_requirements"]) >= 3
        assert reqs["industry"] == "healthcare"
        assert "Patient" in reqs["actors"]
        assert "Doctor" in reqs["actors"]

    def test_domain_model_generated(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        assert len(domain["entities"]) >= 3
        assert len(domain["bounded_contexts"]) >= 3

    def test_business_capabilities_generated(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        assert len(domain["capabilities"]) >= 3

    def test_microservices_generated(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        arch = ArchitectureIntelligence.generate(reqs, domain)
        assert len(arch["services"]) >= 3

    def test_database_generated(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        db = DatabaseDesigner.design(domain)
        assert len(db["tables"]) >= 3
        assert db["migration_strategy"]["tool"] == "Alembic"

    def test_api_contracts_generated(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        arch = ArchitectureIntelligence.generate(reqs, domain)
        apis = ApiIntelligence.generate(arch, domain)
        assert apis["total_endpoints"] >= 5

    def test_event_architecture_generated(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        evts = EventArchitecture.generate(domain)
        assert evts["total_events"] >= 5

    def test_technology_recommendations_generated(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        tech = TechnologyDecisionEngine.recommend(reqs)
        assert len(tech["decisions"]) >= 5

    def test_engineering_backlog_generated(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        arch = ArchitectureIntelligence.generate(reqs, domain)
        plan = EngineeringPlanner.generate(reqs, domain, arch)
        assert plan["total_epics"] >= 1
        assert plan["total_stories"] >= 1

    def test_missions_generated(self):
        reqs = RequirementIntelligence.analyze(HOSPITAL_INPUT)
        domain = DomainIntelligence.generate(reqs)
        arch = ArchitectureIntelligence.generate(reqs, domain)
        plan = EngineeringPlanner.generate(reqs, domain, arch)
        assert len(plan["missions"]) >= 1

    @pytest.mark.asyncio
    async def test_full_analysis_pipeline(self, ai):
        proj = await ai.create_project(
            name="Hospital Management System",
            description="E2E validation scenario",
            input_text=HOSPITAL_INPUT,
        )
        result = await ai.analyze(proj["project_id"])
        assert result["status"] == "analyzed"
        assert result["industry"] == "healthcare"
        assert result["requirements"]["industry"] == "healthcare"
        assert len(result["domain"]["entities"]) > 0
        assert len(result["architecture"]["services"]) > 0
        assert result["database"]["migration_strategy"]["tool"] == "Alembic"
        assert result["apis"]["total_endpoints"] > 0
        assert result["events"]["total_events"] > 0
        assert result["plan"]["total_epics"] > 0
        assert len(result["plan"]["missions"]) > 0

    @pytest.mark.asyncio
    async def test_graph_integration(self, ai):
        proj = await ai.create_project(name="Graph Test", input_text=HOSPITAL_INPUT)
        result = await ai.analyze(proj["project_id"])
        graph = await ai.get_graph(proj["project_id"])
        assert len(graph["entities"]) > 0
        assert len(graph["services"]) > 0
        assert len(graph["relationships"]) > 0


# =============================================================================
# Dashboard
# =============================================================================

class TestDashboard:
    @pytest.mark.asyncio
    async def test_dashboard_empty(self, ai):
        stats = await ai.get_dashboard_stats()
        assert stats["total_projects"] == 0
        assert stats["analyzed"] == 0

    @pytest.mark.asyncio
    async def test_dashboard_with_projects(self, ai):
        await ai.create_project(name="P1")
        p2 = await ai.create_project(name="P2", input_text=HOSPITAL_INPUT)
        p2["status"] = "analyzed"
        p2["industry"] = "healthcare"
        ai._projects[p2["project_id"]] = p2
        stats = await ai.get_dashboard_stats()
        assert stats["total_projects"] == 2
        assert stats["analyzed"] == 1
        assert stats["by_industry"].get("healthcare") == 1
