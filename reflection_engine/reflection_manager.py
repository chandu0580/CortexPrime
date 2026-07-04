class ReflectionManager:

    def should_trigger_reflection(
        self,
        state
    ):

        critique_confidence = (
            state.critique_confidence
        )

        optimization_confidence = (
            state.optimization_confidence
        )

        critique_data = (
            state.critique_data
        )

        # ==========================================
        # LOW CONFIDENCE TRIGGER
        # ==========================================

        if critique_confidence < 0.75:

            return True

        # ==========================================
        # HIGH RISK TRIGGER
        # ==========================================

        risk_level = (
            critique_data
            .get("metadata", {})
            .get(
                "overall_risk_level",
                ""
            )
            .lower()
        )

        if risk_level == "high":

            return True

        # ==========================================
        # DEPLOYMENT READINESS CHECK
        # ==========================================

        deployment_readiness = (
            critique_data
            .get("metadata", {})
            .get(
                "deployment_readiness",
                ""
            )
            .lower()
        )

        if deployment_readiness == "low":

            return True

        return False