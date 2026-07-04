import type {
  IntentInput,
  ValidationResult,
  NormalizedIntent,
  MissionContext,
  MissionAssessment,
  MissionPreview,
  MissionAnalysis,
} from "@/types/intelligence"

function generateId(): string {
  return `intent-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`
}

function detectDomain(text: string): string | null {
  const domains: { keyword: string; domain: string }[] = [
    { keyword: "customer", domain: "Customer Experience" },
    { keyword: "revenue", domain: "Revenue Growth" },
    { keyword: "cost", domain: "Cost Optimization" },
    { keyword: "security", domain: "Security & Compliance" },
    { keyword: "data", domain: "Data & Analytics" },
    { keyword: "market", domain: "Market Expansion" },
    { keyword: "product", domain: "Product Development" },
    { keyword: "operation", domain: "Operational Excellence" },
    { keyword: "employee", domain: "Talent & Culture" },
    { keyword: "innovation", domain: "Innovation & R&D" },
  ]

  const lower = text.toLowerCase()
  const matched = domains.find((d) => lower.includes(d.keyword))
  return matched?.domain ?? null
}

function inferPriority(text: string): "low" | "medium" | "high" | "critical" {
  const lower = text.toLowerCase()
  if (lower.includes("critical") || lower.includes("urgent") || lower.includes("emergency")) return "critical"
  if (lower.includes("important") || lower.includes("key") || lower.includes("major")) return "high"
  if (lower.includes("maybe") || lower.includes("someday") || lower.includes("eventually")) return "low"
  return "medium"
}

function estimateDuration(priority: string): string {
  switch (priority) {
    case "critical": return "1-2 weeks"
    case "high": return "3-4 weeks"
    case "medium": return "1-2 months"
    case "low": return "3-6 months"
    default: return "TBD"
  }
}

function extractSuggestedCapabilities(text: string): string[] {
  const capabilities: string[] = []
  const lower = text.toLowerCase()

  if (lower.includes("analy") || lower.includes("insight")) capabilities.push("Data Analysis")
  if (lower.includes("automate") || lower.includes("workflow")) capabilities.push("Process Automation")
  if (lower.includes("search") || lower.includes("retriev")) capabilities.push("Knowledge Retrieval")
  if (lower.includes("conversation") || lower.includes("chat")) capabilities.push("Conversational AI")
  if (lower.includes("monitor") || lower.includes("detect")) capabilities.push("Monitoring & Alerting")

  if (capabilities.length === 0) {
    capabilities.push("Task Execution")
    capabilities.push("Research & Analysis")
    capabilities.push("Document Processing")
  }

  return capabilities
}

export const intelligenceService = {
  async validateIntent(input: IntentInput): Promise<ValidationResult> {
    const issues: ValidationResult["issues"] = []

    if (!input.text || input.text.trim().length === 0) {
      issues.push({ field: "text", message: "Intent text is required", severity: "error" })
    } else {
      if (input.text.trim().length < 10) {
        issues.push({ field: "text", message: "Intent text is very short; consider adding more detail", severity: "warning" })
      }
      if (input.text.trim().length > 5000) {
        issues.push({ field: "text", message: "Intent text exceeds recommended length of 5000 characters", severity: "warning" })
      }
    }

    if (!input.timestamp) {
      issues.push({ field: "timestamp", message: "Timestamp is required", severity: "error" })
    }

    return {
      valid: issues.filter((i) => i.severity === "error").length === 0,
      issues,
      normalized: issues.filter((i) => i.severity === "error").length === 0
        ? input.text.trim().replace(/\s+/g, " ")
        : undefined,
    }
  },

  async normalizeIntent(input: IntentInput): Promise<NormalizedIntent> {
    const text = input.text.trim().replace(/\s+/g, " ")
    const domain = detectDomain(text)

    return {
      id: generateId(),
      originalText: input.text,
      normalizedText: text,
      domain,
      confidence: domain ? 0.75 : 0.4,
      timestamp: input.timestamp,
    }
  },

  async analyzeContext(intent: NormalizedIntent): Promise<MissionContext> {
    const priority = inferPriority(intent.normalizedText)

    return {
      businessGoal: intent.normalizedText.length > 80
        ? intent.normalizedText.substring(0, 80) + "..."
        : intent.normalizedText,
      constraints: [
        "Resource availability within current cycle",
        "Alignment with existing portfolio objectives",
        "Compliance with enterprise governance policies",
      ],
      successCriteria: [
        "Objective clearly defined and measurable",
        "Stakeholder alignment achieved",
        "Execution plan reviewed and approved",
      ],
      stakeholders: ["Business Owner", "Technical Lead", "Subject Matter Expert"],
      priority,
      businessDomain: intent.domain ?? "General",
    }
  },

  async assessOpportunity(intent: NormalizedIntent, context: MissionContext): Promise<MissionAssessment> {
    const priorityScore = { low: 0.4, medium: 0.6, high: 0.8, critical: 0.95 }
    const feasibility = priorityScore[context.priority]

    return {
      feasibility,
      estimatedDuration: estimateDuration(context.priority),
      resourceRequirements: [
        `${context.businessDomain} domain expert`,
        "Software engineering support",
        "Project management oversight",
      ],
      risks: [
        "Scope creep without clearly defined boundaries",
        "Resource contention with existing commitments",
        "Stakeholder misalignment on success criteria",
      ],
      recommendations: [
        "Define measurable key results before execution",
        "Schedule initial stakeholder alignment session",
        "Identify and document known constraints early",
      ],
      readiness: "assessed",
    }
  },

  async buildPreview(
    intent: NormalizedIntent,
    _context: MissionContext,
    assessment: MissionAssessment,
  ): Promise<MissionPreview> {
    const capabilities = extractSuggestedCapabilities(intent.normalizedText)

    return {
      title: intent.normalizedText.length > 60
        ? intent.normalizedText.substring(0, 57) + "..."
        : intent.normalizedText,
      summary: `Mission to address: "${intent.normalizedText}". This initiative has been assessed with a feasibility score of ${Math.round(assessment.feasibility * 100)}%, indicating ${assessment.feasibility >= 0.8 ? "strong" : "moderate"} alignment with enterprise objectives.`,
      objectives: [
        "Define and validate clear mission objectives",
        "Identify and allocate required resources",
        "Establish success criteria and measurement framework",
        "Execute within defined constraints and timeline",
      ],
      expectedOutcomes: [
        "Achievement of defined business goal",
        "Documented learnings and knowledge artifacts",
        "Measurable impact on enterprise objectives",
      ],
      estimatedEffort: assessment.estimatedDuration,
      suggestedCapabilities: capabilities,
    }
  },

  async analyzeIntent(input: IntentInput): Promise<MissionAnalysis> {
    const validation = await intelligenceService.validateIntent(input)
    if (!validation.valid) {
      throw new Error(`Intent validation failed: ${validation.issues.map((i) => i.message).join("; ")}`)
    }

    const intent = await intelligenceService.normalizeIntent(input)
    const context = await intelligenceService.analyzeContext(intent)
    const assessment = await intelligenceService.assessOpportunity(intent, context)
    const preview = await intelligenceService.buildPreview(intent, context, assessment)

    return {
      intentId: intent.id,
      intent,
      context,
      assessment,
      preview,
      timestamp: new Date().toISOString(),
    }
  },
}
