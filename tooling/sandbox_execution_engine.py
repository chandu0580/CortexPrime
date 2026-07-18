import logging
import subprocess
import tempfile
import os

log = logging.getLogger(__name__)


# ==========================================
# SANDBOX EXECUTION ENGINE
# ==========================================

class SandboxExecutionEngine:

    def __init__(self):

        self.execution_timeout = 10

        self.blocked_keywords = [

            "os.remove",
            "os.rmdir",
            "shutil.rmtree",
            "subprocess.Popen",
            "subprocess.call",
            "subprocess.run",
            "eval(",
            "exec(",
            "__import__",
            "open(",
            "socket",
            "requests",
            "urllib",
            "sys.exit"
        ]

    # ==========================================
    # VALIDATE CODE SAFETY
    # ==========================================

    def validate_code(
        self,
        code: str
    ):

        for keyword in (
            self.blocked_keywords
        ):

            if keyword in code:

                return {

                    "safe": False,

                    "reason": (
                        f"Blocked keyword detected: "
                        f"{keyword}"
                    )
                }

        return {

            "safe": True,

            "reason": None
        }

    # ==========================================
    # EXECUTE CODE SAFELY
    # ==========================================

    def execute_code(
        self,
        code: str
    ):

        log.info(
            "Sandbox Execution "
            "Engine Activated..."
        )

        # ==========================================
        # VALIDATE SAFETY
        # ==========================================

        validation = (
            self.validate_code(
                code
            )
        )

        if not validation["safe"]:

            return {

                "status": "blocked",

                "stdout": "",

                "stderr": (
                    validation["reason"]
                ),

                "return_code": -1
            }

        # ==========================================
        # CREATE TEMP FILE
        # ==========================================

        temp_file = tempfile.NamedTemporaryFile(

            suffix=".py",

            delete=False,

            mode="w",

            encoding="utf-8"
        )

        temp_file.write(code)

        temp_file.close()

        try:

            # ==========================================
            # EXECUTE SANDBOXED CODE
            # ==========================================

            result = subprocess.run(

                ["python", temp_file.name],

                capture_output=True,

                text=True,

                timeout=self.execution_timeout
            )

            return {

                "status": "success",

                "stdout": result.stdout,

                "stderr": result.stderr,

                "return_code": result.returncode
            }

        except subprocess.TimeoutExpired:

            return {

                "status": "timeout",

                "stdout": "",

                "stderr": (
                    "Execution timeout exceeded."
                ),

                "return_code": -1
            }

        except Exception as error:

            return {

                "status": "failed",

                "stdout": "",

                "stderr": str(error),

                "return_code": -1
            }

        finally:

            # ==========================================
            # CLEANUP TEMP FILE
            # ==========================================

            if os.path.exists(
                temp_file.name
            ):

                os.remove(
                    temp_file.name
                )
