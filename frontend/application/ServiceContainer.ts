import { DependencyContainer } from "./DependencyContainer"
import { CortexPlatform } from "@/platform-assembly/CortexPlatform"
import { CortexRuntime } from "@/cortex-runtime/CortexRuntime"
import { PlatformValidation } from "@/platform-validation/PlatformValidation"

export const ServiceContainer = {
  async registerAll(): Promise<void> {
    await DependencyContainer.register("CortexPlatform", new CortexPlatform(), true)
    await DependencyContainer.register("CortexRuntime", new CortexRuntime(), true)
    await DependencyContainer.register("PlatformValidation", new PlatformValidation(), true)
  },

  async getPlatform(): Promise<CortexPlatform | null> {
    return DependencyContainer.resolve<CortexPlatform>("CortexPlatform")
  },

  async getRuntime(): Promise<CortexRuntime | null> {
    return DependencyContainer.resolve<CortexRuntime>("CortexRuntime")
  },

  async getValidation(): Promise<PlatformValidation | null> {
    return DependencyContainer.resolve<PlatformValidation>("PlatformValidation")
  },
}