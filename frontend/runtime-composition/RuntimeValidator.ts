import type { RuntimeValidation } from "./types"
import { RuntimeDependencyResolver } from "./RuntimeDependencyResolver"
import { RuntimeLifecycle } from "./RuntimeLifecycle"
import { RuntimeCoordinator } from "./RuntimeCoordinator"
import { generateId } from "./shared"

export const RuntimeValidator = {
  async validateModuleReadiness(): Promise<{ valid: boolean; errors: string[] }> {
    const order = await RuntimeDependencyResolver.generateExecutionOrder()
    if (!order.valid) return { valid: false, errors: ["execution order not valid"] }
    return { valid: true, errors: [] }
  },

  async validateDependencyIntegrity(): Promise<{ valid: boolean; errors: string[] }> {
    return RuntimeDependencyResolver.validateDependencyGraph()
  },

  async validateExecutionOrder(): Promise<{ valid: boolean; errors: string[] }> {
    const order = await RuntimeDependencyResolver.generateExecutionOrder()
    if (!order.valid) return { valid: false, errors: ["invalid execution order"] }
    if (order.moduleIds.length === 0) return { valid: false, errors: ["execution order is empty"] }
    return { valid: true, errors: [] }
  },

  async validateLifecycle(): Promise<{ valid: boolean; errors: string[] }> {
    const transitions = await RuntimeLifecycle.getTransitions()
    if (transitions.length === 0) return { valid: false, errors: ["no lifecycle transitions recorded"] }
    return { valid: true, errors: [] }
  },

  async validateRuntimeHealth(): Promise<{ valid: boolean; errors: string[] }> {
    const depResult = await this.validateDependencyIntegrity()
    const orderResult = await this.validateExecutionOrder()
    return { valid: depResult.valid && orderResult.valid, errors: [...depResult.errors, ...orderResult.errors] }
  },

  async validateAll(): Promise<RuntimeValidation> {
    const errors: string[] = []
    const warnings: string[] = []

    const mr = await this.validateModuleReadiness()
    if (!mr.valid) errors.push(...mr.errors)

    const di = await this.validateDependencyIntegrity()
    if (!di.valid) errors.push(...di.errors)

    const eo = await this.validateExecutionOrder()
    if (!eo.valid) errors.push(...eo.errors)

    const lc = await this.validateLifecycle()
    if (!lc.valid) warnings.push(...lc.errors)

    const rh = await this.validateRuntimeHealth()
    if (!rh.valid) errors.push(...rh.errors)

    return {
      id: generateId("rtval"), compositionId: "runtime",
      moduleReadiness: mr.valid, dependencyIntegrity: di.valid,
      executionOrderValid: eo.valid, lifecycleValid: lc.valid, runtimeHealth: rh.valid,
      errors, warnings, timestamp: new Date().toISOString(),
    }
  },
}
