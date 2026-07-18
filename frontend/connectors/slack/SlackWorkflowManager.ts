import { SlackWorkflow, SlackWorkflowStep, WorkflowStatus } from "./types"
import { SlackClient } from "./SlackClient"

const workflows: SlackWorkflow[] = []

export const SlackWorkflowManager = {
  async registerWorkflow(workspaceId: string, name: string, description: string = "", steps: SlackWorkflowStep[] = []): Promise<SlackWorkflow> {
    const now = new Date().toISOString()
    const workflow: SlackWorkflow = {
      id: `${Date.now()}`, workspaceId, name, description,
      steps: steps.map((s, i) => ({ ...s, id: s.id || `${Date.now()}_${i}`, workflowId: `${Date.now()}`, position: i })),
      status: WorkflowStatus.DRAFT, createdAt: now, updatedAt: now,
    }
    workflows.push(workflow)
    return { ...workflow }
  },

  async startWorkflow(workflowId: string): Promise<SlackWorkflow | null> {
    const wf = workflows.find((w) => w.id === workflowId)
    if (!wf) return null
    wf.status = WorkflowStatus.ACTIVE
    wf.updatedAt = new Date().toISOString()
    for (const step of wf.steps) {
      const body: Record<string, unknown> = { workflow_id: workflowId, step_id: step.id }
      if (step.config) body.inputs = step.config as Record<string, unknown>
      await SlackClient.post("/workflows.step.started", body)
    }
    return { ...wf }
  },

  async completeWorkflow(workflowId: string): Promise<SlackWorkflow | null> {
    const wf = workflows.find((w) => w.id === workflowId)
    if (!wf) return null
    wf.status = WorkflowStatus.COMPLETED
    wf.updatedAt = new Date().toISOString()
    return { ...wf }
  },

  async listWorkflows(workspaceId: string): Promise<SlackWorkflow[]> {
    return workflows.filter((w) => w.workspaceId === workspaceId).map((w) => ({ ...w }))
  },

  async getWorkflow(id: string): Promise<SlackWorkflow | null> {
    return workflows.find((w) => w.id === id) ?? null
  },
}