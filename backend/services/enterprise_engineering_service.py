"""
Enterprise Engineering Department — DEPRECATED compatibility wrapper.

All functionality has been merged into EnterpriseEngineeringExecutive
in enterprise_engineering_executive.py. This module re-exports the agents
and the EngineeringExecutive class for backward compatibility.

The canonical singleton is `get_engineering_executive()` from
enterprise_engineering_executive.py.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.services.enterprise_engineering_executive import (
    BugInvestigator,
    BuildEngineer,
    CodeGenerator,
    CodeReviewer,
    DevOpsEngineer,
    EngineeringPlanner,
    QAEngineer,
    RepositoryAnalyst,
    SecurityEngineer,
    SoftwareArchitect,
    SREEngineer,
    TestValidator,
    get_engineering_executive,
)

log = logging.getLogger(__name__)

# Re-export event constants for backward compatibility
ENGINEERING_EVENT_PREFIX = "engineering."
ENGINEERING_EVENT_REPO_ANALYZED       = ENGINEERING_EVENT_PREFIX + "repo_analyzed"
ENGINEERING_EVENT_BUILD_COMPLETED     = ENGINEERING_EVENT_PREFIX + "build_completed"
ENGINEERING_EVENT_TEST_COMPLETED      = ENGINEERING_EVENT_PREFIX + "test_completed"
ENGINEERING_EVENT_SECURITY_SCANNED    = ENGINEERING_EVENT_PREFIX + "security_scanned"
ENGINEERING_EVENT_ARCHITECTURE_REVIEWED = ENGINEERING_EVENT_PREFIX + "architecture_reviewed"
ENGINEERING_EVENT_RCA_COMPLETED       = ENGINEERING_EVENT_PREFIX + "rca_completed"
ENGINEERING_EVENT_PLAN_GENERATED      = ENGINEERING_EVENT_PREFIX + "plan_generated"
ENGINEERING_EVENT_CODE_GENERATED      = ENGINEERING_EVENT_PREFIX + "code_generated"
ENGINEERING_EVENT_CODE_REVIEWED       = ENGINEERING_EVENT_PREFIX + "code_reviewed"



class EngineeringExecutive:
    """
    DEPRECATED — delegates to EnterpriseEngineeringExecutive.

    Kept for backward compatibility. Use get_engineering_executive()
    from enterprise_engineering_executive instead.
    """

    def __init__(self) -> None:
        self._delegate = get_engineering_executive()
        self.repository_analyst = RepositoryAnalyst()
        self.build_engineer = BuildEngineer()
        self.qa_engineer = QAEngineer()
        self.security_engineer = SecurityEngineer()
        self.software_architect = SoftwareArchitect()
        self.bug_investigator = BugInvestigator()
        self.engineering_planner = EngineeringPlanner()
        self.code_generator = CodeGenerator()
        self.code_reviewer = CodeReviewer()
        self.test_validator = TestValidator()
        self.devops_engineer = DevOpsEngineer()
        self.sre_engineer = SREEngineer()

    async def execute_engineering_task(
        self,
        objective: str,
        repo_url: str = "",
        branch: str = "main",
        ecosystem: str = "python",
        execution_id: str = "",
        build_diagnostics: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        return await self._delegate.execute_engineering_task(
            objective=objective,
            repo_url=repo_url,
            branch=branch,
            ecosystem=ecosystem,
            execution_id=execution_id,
            build_diagnostics=build_diagnostics,
        )


# Singleton — kept for backward compatibility
engineering_executive = EngineeringExecutive()
