from tooling.sandbox_execution_engine import (
    SandboxExecutionEngine
)


# ==========================================
# CODE EXECUTION TOOL
# ==========================================

class CodeExecutionTool:

    def __init__(self):

        self.sandbox_engine = (
            SandboxExecutionEngine()
        )

    # ==========================================
    # EXECUTE CODE
    # ==========================================

    def execute(
        self,
        tool_input: dict
    ):

        code = tool_input.get(
            "code",
            ""
        )

        language = tool_input.get(
            "language",
            "python"
        )

        if not code:

            raise Exception(
                "Missing code input."
            )

        print(
            f"\n⚙️ Executing "
            f"{language} Code...\n"
        )

        # ==========================================
        # PYTHON EXECUTION
        # ==========================================

        if language == "python":

            sandbox_result = (

                self.sandbox_engine.execute_code(
                    code
                )
            )

            return {

                "tool": (
                    "code_execution"
                ),

                "language": language,

                "result": sandbox_result
            }

        # ==========================================
        # UNSUPPORTED LANGUAGE
        # ==========================================

        raise Exception(

            f"Unsupported language: "
            f"{language}"
        )