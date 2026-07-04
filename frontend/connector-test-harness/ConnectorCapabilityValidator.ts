import { TestStatus, type ConnectorCapabilityResult } from "./types"

export const ConnectorCapabilityValidator = {
  async validateCapabilityCount(capabilities: unknown[], expected: number): Promise<{ valid: boolean; count: number }> {
    return { valid: capabilities.length === expected, count: capabilities.length }
  },

  async validateCapabilityNames(capabilities: { name: string }[]): Promise<{ valid: boolean; invalidNames: string[] }> {
    const invalidNames = capabilities.filter((c) => !c.name || !c.name.includes(".")).map((c) => c.name)
    return { valid: invalidNames.length === 0, invalidNames }
  },

  async validateDuplicates(capabilities: { name: string }[]): Promise<{ hasDuplicates: boolean; duplicates: string[] }> {
    const seen = new Map<string, number>()
    for (const c of capabilities) {
      seen.set(c.name, (seen.get(c.name) ?? 0) + 1)
    }
    const duplicates = Array.from(seen.entries()).filter(([, count]) => count > 1).map(([name]) => name)
    return { hasDuplicates: duplicates.length > 0, duplicates }
  },

  async validateStageMapping(capabilities: { name: string }[], stages: string[]): Promise<{ valid: boolean; unassigned: string[] }> {
    const unassigned = capabilities.filter((c) => !stages.some((s) => c.name.startsWith(s))).map((c) => c.name)
    return { valid: unassigned.length === 0, unassigned }
  },

  async validate(
    capabilities: { name: string; id: string; version: string; enabled: boolean }[],
    expectedCount: number,
    stages: string[],
  ): Promise<ConnectorCapabilityResult> {
    const errors: string[] = []
    const countResult = await this.validateCapabilityCount(capabilities, expectedCount)
    if (!countResult.valid) errors.push(`expected ${expectedCount} capabilities, found ${countResult.count}`)

    const nameResult = await this.validateCapabilityNames(capabilities)
    if (!nameResult.valid) errors.push(`invalid capability names: ${nameResult.invalidNames.join(", ")}`)

    const dupResult = await this.validateDuplicates(capabilities)
    if (dupResult.hasDuplicates) errors.push(`duplicate capabilities: ${dupResult.duplicates.join(", ")}`)

    const stageResult = await this.validateStageMapping(capabilities, stages)
    if (!stageResult.valid) errors.push(`unmapped capabilities: ${stageResult.unassigned.join(", ")}`)

    const status: TestStatus = errors.length === 0 ? TestStatus.PASSED : TestStatus.FAILED
    return {
      totalCapabilities: countResult.count,
      expectedCapabilities: expectedCount,
      namesValid: nameResult.valid,
      duplicatesFound: dupResult.hasDuplicates,
      stageMappingValid: stageResult.valid,
      capabilities: capabilities.map((c) => c.name),
      status,
      errors,
    }
  },
}