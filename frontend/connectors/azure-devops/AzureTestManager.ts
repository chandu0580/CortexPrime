import { type AzureTestPlan, type AzureTestSuite, type AzureTestCase, TestStatus } from "./types"
import { AzureDevOpsClient } from "./AzureDevOpsClient"

export const AzureTestManager = {
  async createTestPlan(projectId: string, name: string, description: string = ""): Promise<AzureTestPlan | null> {
    const result = await AzureDevOpsClient.post<Record<string, unknown>>(`/${projectId}/_apis/test/plans`, { name, description })
    if (result.success && result.data) return { id: String(result.data.id), projectId, name, description: String(result.data.description ?? ""), suites: [], createdAt: String(result.data.createdDate ?? ""), updatedAt: String(result.data.updatedDate ?? "") }
    return null
  },

  async createTestSuite(projectId: string, testPlanId: string, name: string): Promise<AzureTestSuite | null> {
    const result = await AzureDevOpsClient.post<Record<string, unknown>>(`/${projectId}/_apis/test/plans/${testPlanId}/suites`, { name, suiteType: "StaticTestSuite" })
    if (result.success && result.data) return { id: String(result.data.id), testPlanId, name, description: String(result.data.description ?? ""), testCases: [], createdAt: "", updatedAt: "" }
    return null
  },

  async createTestCase(projectId: string, testSuiteId: string, title: string, description: string, steps: string[], expectedResult: string): Promise<AzureTestCase | null> {
    const body = [{ op: "add", path: "/fields/System.Title", value: title }, { op: "add", path: "/fields/Microsoft.VSTS.TCM.Steps", value: steps.join("\n") }, { op: "add", path: "/fields/Microsoft.VSTS.Common.AcceptanceCriteria", value: expectedResult }]
    const result = await AzureDevOpsClient.post<Record<string, unknown>>(`/${projectId}/_apis/wit/workitems/$TestCase`, body)
    if (result.success && result.data) {
      const tc: AzureTestCase = { id: String(result.data.id), testSuiteId, title, description, steps, expectedResult, status: TestStatus.NOT_RUN, assignedTo: null, createdAt: "", updatedAt: "" }
      await AzureDevOpsClient.post(`/${projectId}/_apis/test/plans/suites/${testSuiteId}/testcases/${tc.id}`, {})
      return tc
    }
    return null
  },

  async updateTestResult(projectId: string, testRunId: string, testCaseId: string, status: TestStatus): Promise<boolean> {
    const outcome = status === "passed" ? "Passed" : status === "failed" ? "Failed" : status === "blocked" ? "Blocked" : "Pending"
    const body = [{ op: "add", path: "/state", value: "Completed" }, { op: "add", path: "/outcome", value: outcome }]
    const result = await AzureDevOpsClient.patch(`/${projectId}/_apis/test/Runs/${testRunId}/results?resultIds=${testCaseId}`, body)
    return result.success
  },

  async completeTestRun(projectId: string, testRunId: string): Promise<{ passed: number; failed: number; total: number }> {
    const result = await AzureDevOpsClient.patch(`/${projectId}/_apis/test/Runs/${testRunId}`, { state: "Completed" })
    if (result.success) {
      const runResult = await AzureDevOpsClient.get<Record<string, unknown>>(`/${projectId}/_apis/test/Runs/${testRunId}/results?$top=100`)
      if (runResult.success && runResult.data?.value) {
        const results = runResult.data.value as Record<string, unknown>[]
        const passed = results.filter((r) => r.outcome === "Passed").length
        const failed = results.filter((r) => r.outcome === "Failed").length
        return { passed, failed, total: results.length }
      }
    }
    return { passed: 0, failed: 0, total: 0 }
  },

  async listTestRuns(projectId: string): Promise<Record<string, unknown>[]> {
    const result = await AzureDevOpsClient.get<Record<string, unknown>>(`/${projectId}/_apis/test/runs?$top=100`)
    if (result.success && result.data?.value) return result.data.value as Record<string, unknown>[]
    return []
  },

  async getTestPlan(id: string): Promise<AzureTestPlan | null> {
    const parts = id.split("/")
    const projectId = parts[0] ?? ""
    const planId = parts[1] ?? id
    const result = await AzureDevOpsClient.get<Record<string, unknown>>(`/${projectId}/_apis/test/plans/${planId}`)
    if (result.success && result.data) {
      return { id: String(result.data.id), projectId, name: String(result.data.name), description: String(result.data.description ?? ""), suites: [], createdAt: String(result.data.createdDate ?? ""), updatedAt: String(result.data.updatedDate ?? "") }
    }
    return null
  },

  async listTestPlans(projectId: string): Promise<AzureTestPlan[]> {
    const result = await AzureDevOpsClient.get<Record<string, unknown>>(`/${projectId}/_apis/test/plans?$top=100`)
    if (result.success && result.data?.value) {
      return (result.data.value as Record<string, unknown>[]).map((p) => ({
        id: String(p.id), projectId, name: String(p.name), description: String(p.description ?? ""), suites: [], createdAt: String(p.createdDate ?? ""), updatedAt: String(p.updatedDate ?? ""),
      }))
    }
    return []
  },
}