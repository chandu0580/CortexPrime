export type ExecutionStage =
  | "initialized"
  | "queued"
  | "preparing"
  | "executing"
  | "validating"
  | "completed"
  | "failed"
  | "recovering"
  | "rolled_back"

export type NodeType = "phase" | "task" | "checkpoint" | "milestone"

export type EdgeType = "dependency" | "sequence" | "checkpoint"

export type ValidationType = "automatic" | "manual" | "hybrid"

export interface MissionExecutionNode {
  id: string
  sourceDecisionId: string
  sourceCategory: string
  type: NodeType
  label: string
  description: string
  stage: ExecutionStage
  assignedCapability: string | null
  estimatedDuration: string
  metadata: Record<string, string>
}

export interface MissionExecutionEdge {
  id: string
  sourceId: string
  targetId: string
  type: EdgeType
}

export interface MissionExecutionGraph {
  id: string
  nodes: MissionExecutionNode[]
  edges: MissionExecutionEdge[]
  entryNodeIds: string[]
  exitNodeIds: string[]
}

export interface ExecutionCheckpoint {
  id: string
  name: string
  description: string
  nodeId: string
  criteria: string[]
  validationType: ValidationType
}

export interface CapabilityAssignment {
  id: string
  nodeId: string
  capabilityName: string
  priority: number
  prerequisites: string[]
}

export interface TransitionEvent {
  id: string
  fromStage: ExecutionStage
  toStage: ExecutionStage
  timestamp: string
  triggeredBy: string
}

export type StageTransitionMap = Partial<Record<ExecutionStage, ExecutionStage[]>>

export interface ExecutionLifecycle {
  id: string
  currentStage: ExecutionStage
  availableTransitions: StageTransitionMap
  transitionHistory: TransitionEvent[]
}

export interface ExecutionRecoveryPlan {
  id: string
  nodeId: string
  failureScenario: string
  recoveryActions: string[]
  fallbackNodeId: string | null
  estimatedRecoveryTime: string
  autoRecoverable: boolean
}

export interface OrchestrationReport {
  graph: MissionExecutionGraph
  checkpoints: ExecutionCheckpoint[]
  assignments: CapabilityAssignment[]
  lifecycle: ExecutionLifecycle
  recoveryPlans: ExecutionRecoveryPlan[]
  summary: string
  timestamp: string
}
