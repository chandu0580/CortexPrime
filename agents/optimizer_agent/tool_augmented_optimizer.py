import logging

from agents.optimizer_agent.optimizer import OptimizerAgent
from governance.human_approval_manager import HumanApprovalManager
from tooling.autonomous_repair_engine import AutonomousRepairEngine
from tooling.execution_analyzer import ExecutionAnalyzer
from tooling.tool_executor import ToolExecutor

log = logging.getLogger(__name__)


# ==========================================
# TOOL-AUGMENTED OPTIMIZER
# ==========================================

class ToolAugmentedOptimizerAgent:

    def __init__(self):

        self.tool_executor = (
            ToolExecutor()
        )

        self.execution_analyzer = (
            ExecutionAnalyzer()
        )

        self.repair_engine = (
            AutonomousRepairEngine()
        )

        self.approval_manager = (
            HumanApprovalManager()
        )

        self.optimizer_agent = (
            OptimizerAgent()
        )

    # ==========================================
    # EXECUTE OPTIMIZATION
    # ==========================================

    def execute(
        self,
        cognitive_state
    ):

        log.info(
            "Executing "
            "Tool-Augmented Optimization..."
        )

        # ==========================================
        # BASE OPTIMIZATION
        # ==========================================

        optimization_result = (

            self.optimizer_agent.execute(
                cognitive_state
            )
        )

        # ==========================================
        # EXTRACT EXECUTION STRATEGY
        # ==========================================

        execution_strategy = (
            optimization_result.get(
                "optimized_execution_strategy",
                ""
            )
        )

        # ==========================================
        # HUMAN APPROVAL CHECK
        # ==========================================

        approval_result = (

            self.approval_manager.request_approval(
                execution_strategy
            )
        )

        optimization_result[
            "approval_result"
        ] = approval_result

        # ==========================================
        # BLOCK HIGH-RISK EXECUTION
        # ==========================================

        if not approval_result.get(
            "approved"
        ):

            optimization_result[
                "execution_blocked"
            ] = True

            optimization_result[
                "tool_augmented"
            ] = False

            optimization_result[
                "self_healing_enabled"
            ] = False

            return optimization_result

        # ==========================================
        # GENERATE TEST CODE
        # ==========================================

        generated_code = f"""
print("CortexPrime Optimization Test")

print("Execution Strategy:")

print('''{execution_strategy}''')
"""

        # ==========================================
        # EXECUTE GENERATED CODE
        # ==========================================

        tool_result = (

            self.tool_executor.execute_tool(

                tool_name="code_execution",

                tool_input={

                    "language": "python",

                    "code": generated_code
                }
            )
        )

        execution_result = (
            tool_result.get(
                "result",
                {}
            )
        )

        # ==========================================
        # ANALYZE EXECUTION
        # ==========================================

        execution_analysis = (

            self.execution_analyzer.analyze(
                execution_result
            )
        )

        # ==========================================
        # SELF-HEALING EXECUTION
        # ==========================================

        repair_result = None

        repaired_execution = None

        if (

            execution_analysis.get(
                "status"
            ) == "failed"
        ):

            log.info(
                "Attempting "
                "Autonomous Repair..."
            )

            repair_result = (

                self.repair_engine.repair_code(

                    original_code=generated_code,

                    execution_error=(
                        execution_result.get(
                            "stderr",
                            ""
                        )
                    )
                )
            )

            repaired_code = (
                repair_result.get(
                    "repaired_code",
                    ""
                )
            )

            # ==========================================
            # RE-EXECUTE REPAIRED CODE
            # ==========================================

            repaired_execution = (

                self.tool_executor.execute_tool(

                    tool_name="code_execution",

                    tool_input={

                        "language": "python",

                        "code": repaired_code
                    }
                )
            )

        # ==========================================
        # ATTACH EXECUTION RESULTS
        # ==========================================

        optimization_result[
            "execution_validation"
        ] = execution_result

        optimization_result[
            "execution_analysis"
        ] = execution_analysis

        optimization_result[
            "repair_attempt"
        ] = repair_result

        optimization_result[
            "repaired_execution"
        ] = repaired_execution

        optimization_result[
            "tool_augmented"
        ] = True

        optimization_result[
            "self_healing_enabled"
        ] = True

        optimization_result[
            "governance_enabled"
        ] = True

        return optimization_result
