from datetime import datetime


# ==========================================
# HUMAN APPROVAL MANAGER
# ==========================================

class HumanApprovalManager:

    def __init__(self):

        self.high_risk_keywords = [

            "delete",
            "remove",
            "drop database",
            "shutdown",
            "terminate",
            "format disk",
            "network access",
            "external api",
            "write file",
            "modify system",
            "admin access",
            "credential",
            "token",
            "password"
        ]

        self.audit_log = []

    # ==========================================
    # EVALUATE EXECUTION RISK
    # ==========================================

    def evaluate_execution_risk(
        self,
        execution_text: str
    ):

        lowered_text = (
            execution_text.lower()
        )

        for keyword in (
            self.high_risk_keywords
        ):

            if keyword in lowered_text:

                return {

                    "risk_level": "high",

                    "requires_approval": True,

                    "reason": (
                        f"High-risk keyword "
                        f"detected: {keyword}"
                    )
                }

        return {

            "risk_level": "low",

            "requires_approval": False,

            "reason": (
                "Execution classified "
                "as safe."
            )
        }

    # ==========================================
    # REQUEST APPROVAL
    # ==========================================

    def request_approval(
        self,
        execution_text: str
    ):

        print(
            "\n🛡️ Human Approval "
            "Layer Activated...\n"
        )

        evaluation = (
            self.evaluate_execution_risk(
                execution_text
            )
        )

        audit_entry = {

            "timestamp": (
                datetime.utcnow()
                .isoformat()
            ),

            "execution_text": (
                execution_text
            ),

            "risk_level": (
                evaluation[
                    "risk_level"
                ]
            ),

            "requires_approval": (
                evaluation[
                    "requires_approval"
                ]
            ),

            "reason": (
                evaluation[
                    "reason"
                ]
            )
        }

        self.audit_log.append(
            audit_entry
        )

        # ==========================================
        # HIGH-RISK EXECUTION
        # ==========================================

        if evaluation[
            "requires_approval"
        ]:

            print(
                "\n⚠️ Human Approval "
                "Required.\n"
            )

            return {

                "approved": False,

                "status": "pending_human_review",

                "evaluation": evaluation
            }

        # ==========================================
        # SAFE EXECUTION
        # ==========================================

        print(
            "\n✅ Execution Approved.\n"
        )

        return {

            "approved": True,

            "status": "approved",

            "evaluation": evaluation
        }

    # ==========================================
    # GET AUDIT LOGS
    # ==========================================

    def get_audit_logs(self):

        return self.audit_log