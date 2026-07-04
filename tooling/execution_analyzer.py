# ==========================================
# EXECUTION ANALYZER
# ==========================================

class ExecutionAnalyzer:

    def __init__(self):

        self.known_errors = {

            "SyntaxError": (
                "Python syntax issue detected."
            ),

            "NameError": (
                "Undefined variable or function."
            ),

            "TypeError": (
                "Invalid data type operation."
            ),

            "ImportError": (
                "Missing dependency or module."
            ),

            "ModuleNotFoundError": (
                "Required module not installed."
            ),

            "IndexError": (
                "List index out of range."
            ),

            "KeyError": (
                "Dictionary key missing."
            ),

            "AttributeError": (
                "Object attribute missing."
            ),

            "ZeroDivisionError": (
                "Division by zero detected."
            ),

            "TimeoutExpired": (
                "Execution timeout exceeded."
            )
        }

    # ==========================================
    # ANALYZE EXECUTION RESULT
    # ==========================================

    def analyze(
        self,
        execution_result: dict
    ):

        stderr = execution_result.get(
            "stderr",
            ""
        )

        stdout = execution_result.get(
            "stdout",
            ""
        )

        return_code = execution_result.get(
            "return_code",
            0
        )

        # ==========================================
        # SUCCESS CASE
        # ==========================================

        if return_code == 0:

            return {

                "status": "success",

                "analysis": (
                    "Execution completed "
                    "successfully."
                ),

                "stdout": stdout,

                "stderr": stderr,

                "recovery_suggestion": None
            }

        # ==========================================
        # ERROR DETECTION
        # ==========================================

        detected_error = (
            self.detect_error_type(
                stderr
            )
        )

        # ==========================================
        # BUILD ANALYSIS
        # ==========================================

        return {

            "status": "failed",

            "error_type": detected_error,

            "analysis": self.known_errors.get(

                detected_error,

                "Unknown execution failure."
            ),

            "stdout": stdout,

            "stderr": stderr,

            "recovery_suggestion": (

                self.generate_recovery_suggestion(
                    detected_error
                )
            )
        }

    # ==========================================
    # DETECT ERROR TYPE
    # ==========================================

    def detect_error_type(
        self,
        stderr: str
    ):

        for error_name in (
            self.known_errors.keys()
        ):

            if error_name in stderr:

                return error_name

        return "UnknownError"

    # ==========================================
    # GENERATE RECOVERY SUGGESTION
    # ==========================================

    def generate_recovery_suggestion(
        self,
        error_type: str
    ):

        suggestions = {

            "SyntaxError": (
                "Validate generated Python syntax."
            ),

            "NameError": (
                "Check undefined variables."
            ),

            "TypeError": (
                "Verify datatype compatibility."
            ),

            "ImportError": (
                "Install or validate dependencies."
            ),

            "ModuleNotFoundError": (
                "Install missing Python packages."
            ),

            "IndexError": (
                "Validate list indexing logic."
            ),

            "KeyError": (
                "Check dictionary keys."
            ),

            "AttributeError": (
                "Validate object structure."
            ),

            "ZeroDivisionError": (
                "Protect division operations."
            ),

            "TimeoutExpired": (
                "Optimize execution runtime."
            )
        }

        return suggestions.get(

            error_type,

            "Inspect execution traceback."
        )