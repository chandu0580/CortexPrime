def reflection_router(state):

    print(
        "\n🧠 Evaluating Reflection Routing...\n"
    )

    # ==========================================
    # STOP INFINITE RECURSION
    # ==========================================

    if (
        state.reflection_count
        >= state.max_reflections
    ):

        print(
            "\n🛑 Max Reflection Limit Reached.\n"
        )

        return "optimizer"

    critique_confidence = (
        state.critique_confidence
    )

    deployment_readiness = (
        state.critique_data
        .get("metadata", {})
        .get(
            "deployment_readiness",
            ""
        )
        .lower()
    )

    overall_risk = (
        state.critique_data
        .get("metadata", {})
        .get(
            "overall_risk_level",
            ""
        )
        .lower()
    )

    # ==========================================
    # REFLECTION TRIGGER
    # ==========================================

    if (
        critique_confidence < 0.75
        or deployment_readiness == "low"
        or overall_risk == "high"
    ):

        print(
            "\n🔄 Reflection Route Triggered...\n"
        )

        return "planner_retry"

    print(
        "\n✅ Cognition Stable → Optimization Route\n"
    )

    return "optimizer"