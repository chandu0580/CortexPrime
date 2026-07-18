import { Workflow, WorkflowStep, WorkflowStatus } from "./types"
import { TeamsClient } from "./TeamsClient"

const workflows: Workflow[] = []

export const TeamsWorkflowManager = {
  async registerWorkflow(organizationId: string, name: string, description: string = "", steps: WorkflowStep[] = []): Promise<Workflow> {
    const now = new Date().toISOString()
    const workflow: Workflow = {
      id: `${Date.now()}`, organizationId, name, description,
      steps: steps.map((s, i) => ({ ...s, id: s.id || `${Date.now()}_${i}`, workflowId: `${Date.now()}`, position: i })),
      status: WorkflowStatus.DRAFT, createdAt: now, updatedAt: now,
    }
    workflows.push(workflow)
    return { ...workflow }
  },

  async startWorkflow(workflowId: string): Promise<Workflow | null> {
    const wf = workflows.find((w) => w.id === workflowId)
    if (!wf) return null
    wf.status = WorkflowStatus.ACTIVE
    wf.updatedAt = new Date().toISOString()
    return { ...wf }
  },

  async completeWorkflow(workflowId: string): Promise<Workflow | null> {
    const wf = workflows.find((w) => w.id === workflowId)
    if (!wf) return null
    wf.status = WorkflowStatus.COMPLETED
    wf.updatedAt = new Date().toISOString()
    return { ...wf }
  },

  async getWorkflow(id: string): Promise<Workflow | null> {
    return workflows.find((w) => w.id === id) ?? null
  },

  async listWorkflows(organizationId: string): Promise<Workflow[]> {
    return workflows.filter((w) => w.organizationId === organizationId).map((w) => ({ ...w }))
  },
}