import { useQuery, useMutation } from "@tanstack/react-query"
import {
  enterpriseEngineeringApi,
  EngineeringAgent,
  EngineeringEcosystem,
  EngineeringReport,
  EngineeringAgentResult,
} from "@/services/enterprise/engineering"

export function useEngineeringAgents() {
  return useQuery({
    queryKey: ["engineering-agents"],
    queryFn: async () => {
      const res = await enterpriseEngineeringApi.listAgents()
      return res.agents as EngineeringAgent[]
    },
    staleTime: 300_000,
  })
}

export function useEngineeringEcosystems() {
  return useQuery({
    queryKey: ["engineering-ecosystems"],
    queryFn: async () => {
      const res = await enterpriseEngineeringApi.listEcosystems()
      return res.ecosystems as EngineeringEcosystem[]
    },
    staleTime: 300_000,
  })
}

export function useExecuteEngineeringTask() {
  return useMutation({
    mutationFn: async (payload: {
      objective: string
      repo_url?: string
      branch?: string
      ecosystem?: string
      execution_id?: string
      build_diagnostics?: unknown[]
    }) => {
      return enterpriseEngineeringApi.execute(payload) as Promise<EngineeringReport>
    },
  })
}

export function useAnalyzeRepository() {
  return useMutation({
    mutationFn: async ({ repoUrl, branch, executionId }: { repoUrl: string; branch?: string; executionId?: string }) => {
      return enterpriseEngineeringApi.analyzeRepo(repoUrl, branch, executionId) as Promise<EngineeringAgentResult>
    },
  })
}

export function useBuildPlan() {
  return useMutation({
    mutationFn: async ({ ecosystem, executionId }: { ecosystem?: string; executionId?: string }) => {
      return enterpriseEngineeringApi.buildPlan(ecosystem, executionId) as Promise<EngineeringAgentResult>
    },
  })
}

export function useInvestigate() {
  return useMutation({
    mutationFn: async ({ executionId, buildDiagnostics }: { executionId: string; buildDiagnostics?: unknown[] }) => {
      return enterpriseEngineeringApi.investigate(executionId, buildDiagnostics) as Promise<EngineeringAgentResult>
    },
  })
}

export function useGenerateEngineeringPlan() {
  return useMutation({
    mutationFn: async (payload: {
      objective: string
      repoAnalysis?: unknown
      architectureReview?: unknown
      executionId?: string
    }) => {
      return enterpriseEngineeringApi.generatePlan(
        payload.objective,
        payload.repoAnalysis,
        payload.architectureReview,
        payload.executionId,
      ) as Promise<EngineeringAgentResult>
    },
  })
}
