export enum AgentStatus {
  Idle = 'idle',
  Running = 'running',
  Completed = 'completed',
  Failed = 'failed',
  Paused = 'paused',
  Cancelled = 'cancelled',
}

export interface AgentConfig {
  agentType: string;
  agentName: string;
  version: string;
  description: string;
  tags: string[];
  maxRetries: number;
  timeoutSeconds: number;
  permissions: string[];
}

export interface ToolSpec {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

export interface MissionResult {
  missionId: string;
  status: AgentStatus;
  output: Record<string, unknown>;
  error?: string;
  startedAt?: string;
  completedAt?: string;
  tokenUsage: Record<string, number>;
  artifacts: Record<string, unknown>[];
}

export interface AgentMetadata {
  agentId: string;
  agentType: string;
  agentName: string;
  version: string;
  status: AgentStatus;
  createdAt: string;
  tools: ToolSpec[];
  tags: string[];
}

export interface MissionContext {
  missionId: string;
  orgId?: string;
  userId?: string;
  params: Record<string, unknown>;
}
