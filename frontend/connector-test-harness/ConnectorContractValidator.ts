import { TestStatus, type ConnectorContractResult } from "./types"
import { generateId } from "./shared"

export const ConnectorContractValidator = {
  async validateAbstractConnector(connector: Record<string, unknown>): Promise<boolean> {
    return typeof connector.initialize === "function"
      && typeof connector.shutdown === "function"
      && typeof connector.health === "function"
      && typeof connector.metrics === "function"
      && typeof connector.validate === "function"
      && typeof connector.snapshot === "function"
  },

  async validateRequiredMethods(connector: Record<string, unknown>, expectedMethods: string[]): Promise<{ present: string[]; missing: string[] }> {
    const present = expectedMethods.filter((m) => typeof connector[m] === "function")
    const missing = expectedMethods.filter((m) => typeof connector[m] !== "function")
    return { present, missing }
  },

  async validateRequiredExports(exports: string[], requiredExports: string[]): Promise<{ present: string[]; missing: string[] }> {
    const present = requiredExports.filter((e) => exports.includes(e))
    const missing = requiredExports.filter((e) => !exports.includes(e))
    return { present, missing }
  },

  async validateCapabilityRegistration(capabilities: { name: string }[], expectedNames: string[]): Promise<{ valid: boolean; missing: string[] }> {
    const foundNames = capabilities.map((c) => c.name)
    const missing = expectedNames.filter((n) => !foundNames.includes(n))
    return { valid: missing.length === 0, missing }
  },

  async validate(
    connector: Record<string, unknown>,
    exports: string[],
    capabilities: { name: string }[],
    expectedMethods: string[],
    expectedExports: string[],
    expectedCapabilities: string[],
  ): Promise<ConnectorContractResult> {
    const errors: string[] = []
    const implementsAbstractConnector = await this.validateAbstractConnector(connector)
    if (!implementsAbstractConnector) errors.push("connector does not implement all AbstractConnector methods")

    const { present, missing } = await this.validateRequiredMethods(connector, expectedMethods)
    if (missing.length > 0) errors.push(`missing methods: ${missing.join(", ")}`)

    const exportResult = await this.validateRequiredExports(exports, expectedExports)
    if (exportResult.missing.length > 0) errors.push(`missing exports: ${exportResult.missing.join(", ")}`)

    const capResult = await this.validateCapabilityRegistration(capabilities, expectedCapabilities)
    if (capResult.missing.length > 0) errors.push(`missing capabilities: ${capResult.missing.join(", ")}`)

    const status: TestStatus = errors.length === 0 ? TestStatus.PASSED : TestStatus.FAILED
    return {
      implementsAbstractConnector,
      hasRequiredMethods: missing.length === 0,
      hasRequiredExports: exportResult.missing.length === 0,
      hasCapabilityRegistration: capResult.valid,
      methodsPresent: present,
      methodsMissing: missing,
      status,
      errors,
    }
  },
}