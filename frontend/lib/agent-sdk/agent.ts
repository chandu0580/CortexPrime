import type { AgentConfig, AgentMetadata, MissionContext, MissionResult } from './types';
import { AgentStatus } from './types';
import { getRegisteredTools } from './tool-registry';

export class CortexAgent {
  public readonly agentId: string;
  public status: AgentStatus = AgentStatus.Idle;
  public readonly createdAt: string;
  private _tools = getRegisteredTools();

  constructor(public readonly config: AgentConfig) {
    this.agentId = crypto.randomUUID();
    this.createdAt = new Date().toISOString();
  }

  get agentType(): string {
    return this.config.agentType;
  }

  get name(): string {
    return this.config.agentName;
  }

  metadata(): AgentMetadata {
    return {
      agentId: this.agentId,
      agentType: this.config.agentType,
      agentName: this.config.agentName,
      version: this.config.version,
      status: this.status,
      createdAt: this.createdAt,
      tools: this._tools,
      tags: this.config.tags,
    };
  }

  async execute(context: MissionContext): Promise<MissionResult> {
    throw new Error('Subclasses must implement execute()');
  }

  async run(context: MissionContext): Promise<MissionResult> {
    this.status = AgentStatus.Running;
    const startedAt = new Date().toISOString();
    try {
      const result = await this.execute(context);
      result.missionId = context.missionId;
      result.startedAt = startedAt;
      result.completedAt = new Date().toISOString();
      this.status = result.status;
      return result;
    } catch (error) {
      this.status = AgentStatus.Failed;
      return {
        missionId: context.missionId,
        status: AgentStatus.Failed,
        output: {},
        error: error instanceof Error ? error.message : String(error),
        startedAt,
        completedAt: new Date().toISOString(),
        tokenUsage: {},
        artifacts: [],
      };
    }
  }
}
