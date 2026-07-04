import type { RuntimeModuleRecord } from "./types"
import { RuntimeManifest } from "./RuntimeManifest"
import { RuntimeInitializer } from "./RuntimeInitializer"

export const RuntimeShutdownPipeline = {
  async execute(): Promise<{ modulesDeactivated: number; durationMs: number; errors: string[] }> {
    const modules = await RuntimeManifest.listModules()
    const errors: string[] = []
    const start = Date.now()
    const reverseOrder = [...modules].reverse()
    let deactivated = 0

    for (const mod of reverseOrder) {
      try {
        await RuntimeInitializer.rollback(mod.id, [mod.id])
        deactivated++
      } catch {
        errors.push(`failed to deactivate ${mod.id}`)
      }
    }

    return { modulesDeactivated: deactivated, durationMs: Date.now() - start, errors }
  },
}