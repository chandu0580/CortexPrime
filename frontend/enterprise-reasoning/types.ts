import type { Priority } from "@/types/intelligence"

export type ConfidenceLevel = "high" | "medium" | "low"

export type DecisionCategory =
  | "strategy"
  | "capability"
  | "risk"
  | "dependency"
  | "recommendation"

export interface DecisionConfidence {
  level: ConfidenceLevel
  score: number
  rationale: string
}

export interface DecisionEvidence {
  id: string
  source: string
  content: string
  relevance: string
  confidence: DecisionConfidence
}

export interface DecisionAssumption {
  id: string
  statement: string
  impact: string
  confidence: ConfidenceLevel
}

export interface DecisionAlternative {
  id: string
  title: string
  description: string
  pros: string[]
  cons: string[]
  rationale: string
  confidence: DecisionConfidence
}

export interface ReasoningStep {
  id: string
  order: number
  description: string
  input: string
  output: string
  confidence: DecisionConfidence
}

export interface ReasoningTrace {
  id: string
  steps: ReasoningStep[]
  conclusion: string
  confidence: DecisionConfidence
}

export interface ReasoningExplanation {
  summary: string
  detailed: string
  trace: ReasoningTrace
}

export interface EnterpriseDecision {
  id: string
  category: DecisionCategory
  targetId: string
  targetLabel: string
  explanation: ReasoningExplanation
  evidence: DecisionEvidence[]
  assumptions: DecisionAssumption[]
  alternatives: DecisionAlternative[]
  confidence: DecisionConfidence
  timestamp: string
}

export interface EnterpriseReasoningReport {
  decisions: EnterpriseDecision[]
  summary: string
  traceCount: number
  averageConfidence: number
  timestamp: string
}

// --- LLM Provider Types ---

export type ProviderType =
  | "openai"
  | "azure-openai"
  | "anthropic"
  | "gemini"
  | "ollama"

export type ModelCapability =
  | "reasoning"
  | "planning"
  | "research"
  | "browser"
  | "connector"
  | "incident"
  | "engineering"

export interface ProviderConfig {
  type: ProviderType
  apiKey?: string
  endpoint?: string
  deploymentName?: string
  apiVersion?: string
  model: string
  maxTokens?: number
  temperature?: number
  timeoutMs?: number
}

export interface ReasoningConfig {
  defaultProvider: ProviderType
  providers: ProviderConfig[]
  fallbackOrder: ProviderType[]
  maxRetries: number
  retryDelayMs: number
  streamingEnabled: boolean
}

// --- Structured Output Schemas ---

export interface MissionPlan {
  missionId: string
  title: string
  objective: string
  phases: MissionPhase[]
  keyResults: string[]
  estimatedDuration: string
  priority: Priority
  dependencies: string[]
  risks: string[]
}

export interface MissionPhase {
  id: string
  name: string
  order: number
  description: string
  tasks: MissionTask[]
  estimatedDuration: string
  dependencies: string[]
}

export interface MissionTask {
  id: string
  name: string
  description: string
  assignedRole: string
  estimatedEffort: string
}

export interface WorkerDecision {
  workerId: string
  action: string
  target: string
  parameters: Record<string, unknown>
  priority: Priority
  reasoning: string
  confidence: number
}

export interface ConnectorAction {
  connectorId: string
  action: string
  endpoint: string
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
  payload: Record<string, unknown> | null
  headers: Record<string, string>
  timeoutMs: number
}

export interface BrowserAction {
  action: "navigate" | "click" | "type" | "select" | "extract" | "wait" | "screenshot"
  target: string
  value?: string
  selector?: string
  timeoutMs?: number
  url?: string
}

export interface VoiceResponse {
  text: string
  tone: "neutral" | "empathetic" | "urgent" | "informative" | "instructional"
  contextReferences: string[]
  requiresConfirmation: boolean
  followUpAction: string | null
}

export interface RecoveryDecision {
  sessionId: string
  failureType: string
  recoveryStrategy: "restart" | "retry" | "fallback" | "degrade" | "abort"
  estimatedRecoveryMs: number
  fallbackProvider: ProviderType | null
  requiresUserConfirmation: boolean
}

// --- Reasoning Context ---

export interface ReasoningContext {
  missionId: string
  missionObjective: string
  missionPriority: Priority
  conversationHistory: string[]
  memoryEntries: ReasonedMemoryEntry[]
  knowledgeRelationships: ReasonedRelationship[]
  connectorState: Record<string, unknown>
  workerState: Record<string, unknown>
  additionalContext: Record<string, unknown>
}

export interface ReasonedMemoryEntry {
  id: string
  content: string
  relevance: number
  timestamp: string
}

export interface ReasonedRelationship {
  source: string
  target: string
  relationship: string
  strength: number
}

// --- Provider Response ---

export interface LLMResponse {
  content: string
  structured: Record<string, unknown> | null
  tokensUsed: TokenUsage
  latencyMs: number
  provider: ProviderType
  model: string
  finishReason: string
  timestamp: string
}

export interface TokenUsage {
  prompt: number
  completion: number
  total: number
}

export interface StreamingChunk {
  content: string
  done: boolean
  tokensUsed: TokenUsage | null
  error: string | null
}

// --- Metrics ---

export interface ReasoningMetrics {
  totalRequests: number
  totalTokens: number
  totalCost: number
  averageLatencyMs: number
  requestsByProvider: Record<string, number>
  tokensByProvider: Record<string, number>
  failuresByProvider: Record<string, number>
  retriesByProvider: Record<string, number>
  providerAvailability: Record<string, boolean>
  lastUpdated: string
}

// --- Audit ---

export interface ReasoningAuditEntry {
  id: string
  sessionId: string
  provider: ProviderType
  model: string
  promptHash: string
  promptPreview: string
  responseHash: string
  responsePreview: string
  tokensUsed: TokenUsage
  latencyMs: number
  success: boolean
  error: string | null
  validated: boolean
  schemaType: string | null
  timestamp: string
}

// --- Pipeline ---

export type ReasoningStage =
  | "context_build"
  | "memory_retrieval"
  | "knowledge_retrieval"
  | "connector_context"
  | "prompt_construction"
  | "llm_invocation"
  | "response_validation"
  | "structured_output"

export type PromptType =
  | "mission_planning"
  | "executive_reasoning"
  | "research"
  | "browser_automation"
  | "connector_action"
  | "incident_response"
  | "engineering_operations"
