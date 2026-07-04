import type { PromptType, ReasoningContext } from "./types"

type TemplateVariables = Record<string, string | number | boolean>

function render(template: string, vars: TemplateVariables): string {
  let result = template
  for (const [key, value] of Object.entries(vars)) {
    result = result.replaceAll(`{{${key}}}`, String(value))
  }
  return result
}

export const ReasoningPromptTemplates = {
  getTemplate(type: PromptType, context: ReasoningContext): string {
    const template = this.getRawTemplate(type)
    const vars = this.buildVariables(context)
    return render(template, vars)
  },

  buildVariables(context: ReasoningContext): TemplateVariables {
    return {
      mission_objective: context.missionObjective,
      mission_priority: context.missionPriority,
      conversation_history: context.conversationHistory.join("\n"),
      memory_entries: context.memoryEntries.map((e) => `[${e.relevance}] ${e.content}`).join("\n"),
      knowledge_relationships: context.knowledgeRelationships.map((r) => `${r.source} --${r.relationship}--> ${r.target}`).join("\n"),
      connector_state: JSON.stringify(context.connectorState),
      worker_state: JSON.stringify(context.workerState),
      additional_context: JSON.stringify(context.additionalContext),
    }
  },

  getRawTemplate(type: PromptType): string {
    const templates: Record<PromptType, string> = {
      mission_planning: this.MISSION_PLANNING,
      executive_reasoning: this.EXECUTIVE_REASONING,
      research: this.RESEARCH,
      browser_automation: this.BROWSER_AUTOMATION,
      connector_action: this.CONNECTOR_ACTION,
      incident_response: this.INCIDENT_RESPONSE,
      engineering_operations: this.ENGINEERING_OPERATIONS,
    }
    return templates[type] ?? this.EXECUTIVE_REASONING
  },

  MISSION_PLANNING: `You are an enterprise mission planning system.

Mission Objective: {{mission_objective}}
Priority: {{mission_priority}}

Conversation History:
{{conversation_history}}

Relevant Memory:
{{memory_entries}}

Knowledge Graph Relationships:
{{knowledge_relationships}}

Return a JSON mission plan with: title, objective, phases (id, name, order, description, tasks, estimatedDuration, dependencies), keyResults, estimatedDuration, priority, dependencies, risks.`,

  EXECUTIVE_REASONING: `You are an executive reasoning system.

Context: {{mission_objective}}
Priority: {{mission_priority}}

Memory:
{{memory_entries}}

Knowledge:
{{knowledge_relationships}}

Analyze the situation and provide strategic reasoning. Return structured JSON with: recommendation, reasoning, confidence, alternatives.`,

  RESEARCH: `You are a research analysis system.

Objective: {{mission_objective}}

Available Context:
{{additional_context}}

Memory References:
{{memory_entries}}

Knowledge Graph:
{{knowledge_relationships}}

Research the topic and provide findings. Return structured JSON with: summary, findings (array), sources, confidence, gaps.`,

  BROWSER_AUTOMATION: `You are a browser automation system.

Task Objective: {{mission_objective}}

Worker State:
{{worker_state}}

Connector State:
{{connector_state}}

Determine the browser actions needed. Return structured JSON with: action (navigate/click/type/select/extract/wait/screenshot), target, value, selector, timeoutMs, url.`,

  CONNECTOR_ACTION: `You are an enterprise connector system.

Integration Context:
{{connector_state}}

Mission Context: {{mission_objective}}

Worker State:
{{worker_state}}

Knowledge:
{{knowledge_relationships}}

Determine the connector action to execute. Return structured JSON with: connectorId, action, endpoint, method, payload, headers, timeoutMs.`,

  INCIDENT_RESPONSE: `You are an incident response system.

Incident Context: {{mission_objective}}
Priority: {{mission_priority}}

Situation Memory:
{{memory_entries}}

System State:
{{additional_context}}

Worker State:
{{worker_state}}

Analyze the incident and determine recovery actions. Return structured JSON with: assessment, severity, impact, recoveryStrategy, actions (array), estimatedRecoveryMs, requiresUserConfirmation.`,

  ENGINEERING_OPERATIONS: `You are an engineering operations system.

Operation Objective: {{mission_objective}}

System State:
{{worker_state}}

Memory:
{{memory_entries}}

Knowledge:
{{knowledge_relationships}}

Determine the engineering operations to execute. Return structured JSON with: operation, target, parameters, expectedOutcome, rollbackPlan.`,
}
