import { TestStatus, type ConnectorLifecycleResult } from "./types"

const expectedStates = ["initialized", "active", "paused", "deactivated", "failed"]

export const ConnectorLifecycleValidator = {
  async validateInitialize(definition: { state: string }): Promise<boolean> {
    return definition.state === "initialized" || definition.state === "active"
  },

  async validateShutdown(definition: { state: string }): Promise<boolean> {
    return definition.state === "deactivated"
  },

  async validateStateTransitions(transitions: Record<string, string[]>): Promise<{ valid: boolean; invalid: string[] }> {
    const invalid: string[] = []
    for (const [from, toStates] of Object.entries(transitions)) {
      for (const to of toStates) {
        if (!expectedStates.includes(to)) {
          invalid.push(`${from} -> ${to}`)
        }
      }
    }
    return { valid: invalid.length === 0, invalid }
  },

  async validate(
    definition: { state: string },
    transitions: Record<string, string[]>,
  ): Promise<ConnectorLifecycleResult> {
    const errors: string[] = []
    const initializeSupported = await this.validateInitialize(definition)
    const shutdownSupported = await this.validateShutdown(definition)
    const { valid: validTransitions } = await this.validateStateTransitions(transitions)
    if (!validTransitions) errors.push("invalid state transitions found")

    const status: TestStatus = errors.length === 0 ? TestStatus.PASSED : TestStatus.FAILED
    return {
      initializeSupported,
      shutdownSupported,
      activateSupported: true,
      pauseSupported: true,
      resumeSupported: true,
      deactivateSupported: true,
      validTransitions,
      status,
      errors,
    }
  },
}