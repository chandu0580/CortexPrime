import axios from "axios"
import { apiUrl } from "@/lib/constants"

export interface EngineeringAgent {
  name: string
  title: string
  responsibility: string
}

export interface EngineeringEcosystem {
  id: string
  name: string
  build: string
  lint: string
  typecheck?: string
  test?: string
}

export interface EngineeringAgentResult {
  agent: string
  [key: string]: unknown
}

export interface EngineeringReport {
  execution_id: string
  objective: string
  started_at: string
  completed_at: string
  status: string
  agents: Record<string, EngineeringAgentResult>
  artifacts: Record<string, unknown>
}

export const enterpriseEngineeringApi = {
  execute: async (payload: {
    objective: string
    repo_url?: string
    branch?: string
    ecosystem?: string
    execution_id?: string
    build_diagnostics?: unknown[]
  }): Promise<EngineeringReport> => {
    const res = await axios.post(`${apiUrl}/api/engineering/execute`, payload)
    return res.data
  },

  listAgents: async (): Promise<{ agents: EngineeringAgent[]; total: number }> => {
    const res = await axios.get(`${apiUrl}/api/engineering/agents`)
    return res.data
  },

  listEcosystems: async (): Promise<{ ecosystems: EngineeringEcosystem[]; total: number }> => {
    const res = await axios.get(`${apiUrl}/api/engineering/ecosystems`)
    return res.data
  },

  analyzeRepo: async (repoUrl: string, branch = "main", executionId = ""): Promise<EngineeringAgentResult> => {
    const res = await axios.post(`${apiUrl}/api/engineering/analyze-repo`, {
      repo_url: repoUrl,
      branch,
      execution_id: executionId,
    })
    return res.data
  },

  buildPlan: async (ecosystem = "python", executionId = ""): Promise<EngineeringAgentResult> => {
    const res = await axios.post(`${apiUrl}/api/engineering/build-plan`, {
      ecosystem,
      execution_id: executionId,
    })
    return res.data
  },

  investigate: async (executionId: string, buildDiagnostics?: unknown[]): Promise<EngineeringAgentResult> => {
    const res = await axios.post(`${apiUrl}/api/engineering/investigate`, {
      execution_id: executionId,
      build_diagnostics: buildDiagnostics,
    })
    return res.data
  },

  generatePlan: async (objective: string, repoAnalysis?: unknown, architectureReview?: unknown, executionId = ""): Promise<EngineeringAgentResult> => {
    const res = await axios.post(`${apiUrl}/api/engineering/plan`, {
      objective,
      repo_analysis: repoAnalysis,
      architecture_review: architectureReview,
      execution_id: executionId,
    })
    return res.data
  },
}
