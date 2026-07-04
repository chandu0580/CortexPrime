import { TestStatus, type ConnectorPermissionResult } from "./types"

export const ConnectorPermissionValidator = {
  async validateEvaluatorCount(evaluators: string[], expected: number): Promise<{ valid: boolean; count: number }> {
    return { valid: evaluators.length >= expected, count: evaluators.length }
  },

  async validateEvaluatorNames(evaluators: string[]): Promise<{ valid: boolean; invalidNames: string[] }> {
    const invalidNames = evaluators.filter((e) => !e.startsWith("evaluate"))
    return { valid: invalidNames.length === 0, invalidNames }
  },

  async validate(
    evaluators: string[],
    expectedEvaluators: number,
  ): Promise<ConnectorPermissionResult> {
    const errors: string[] = []
    const countResult = await this.validateEvaluatorCount(evaluators, expectedEvaluators)
    if (!countResult.valid) errors.push(`expected at least ${expectedEvaluators} evaluators, found ${countResult.count}`)

    const nameResult = await this.validateEvaluatorNames(evaluators)
    if (!nameResult.valid) errors.push(`invalid evaluator names: ${nameResult.invalidNames.join(", ")}`)

    const status: TestStatus = errors.length === 0 ? TestStatus.PASSED : TestStatus.FAILED
    return {
      evaluatorCount: countResult.count,
      expectedEvaluators,
      evaluators,
      policyAvailable: countResult.count > 0,
      validationConsistent: nameResult.valid,
      status,
      errors,
    }
  },
}