import type { Priority } from "@/types/intelligence"

export type PhaseStatus = "pending" | "in_progress" | "completed" | "blocked"

export type TaskStatus = "pending" | "in_progress" | "completed" | "blocked"

export type ImpactLevel = "low" | "medium" | "high" | "critical"

export type DependencyType = "blocking" | "sequential" | "parallel"

export type GraphNodeType = "phase" | "task" | "milestone"

export type GraphEdgeType = "dependency" | "sequence" | "containment"

export interface MissionPhase {
  id: string
  name: string
  description: string
  order: number
  status: PhaseStatus
  tasks: MissionTask[]
}

export interface MissionTask {
  id: string
  name: string
  description: string
  assignedCapability: string | null
  estimatedEffort: string
  dependsOn: string[]
  status: TaskStatus
}

export interface MissionCapability {
  id: string
  name: string
  description: string
  required: boolean
  confidence: number
  alternatives: string[]
}

export interface MissionDependency {
  id: string
  sourceId: string
  targetId: string
  type: DependencyType
  description: string
}

export interface MissionRisk {
  id: string
  category: string
  description: string
  likelihood: number
  impact: ImpactLevel
  mitigation: string
  owner: string
}

export interface MissionRecommendation {
  id: string
  category: string
  priority: Priority
  description: string
  rationale: string
  actionItems: string[]
}

export interface MissionStrategy {
  id: string
  title: string
  objective: string
  approach: string
  phases: MissionPhase[]
  timeline: string
  priority: Priority
  keyResults: string[]
  recommendations: MissionRecommendation[]
}

export interface MissionPlan {
  id: string
  strategyId: string
  phases: MissionPhase[]
  tasks: MissionTask[]
  dependencies: MissionDependency[]
  capabilities: MissionCapability[]
  risks: MissionRisk[]
  estimatedDuration: string
  resourceAllocation: Record<string, number>
}

export interface MissionGraphNode {
  id: string
  type: GraphNodeType
  label: string
  metadata: Record<string, string>
}

export interface MissionGraphEdge {
  id: string
  sourceId: string
  targetId: string
  type: GraphEdgeType
}

export interface MissionGraph {
  nodes: MissionGraphNode[]
  edges: MissionGraphEdge[]
}

export interface MissionIntelligenceReport {
  strategy: MissionStrategy
  plan: MissionPlan
  capabilities: MissionCapability[]
  risks: MissionRisk[]
  graph: MissionGraph
  timestamp: string
}
