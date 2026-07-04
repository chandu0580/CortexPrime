import type { ApplicationEnvironment, ApplicationEnvironmentType } from "./types"
import { ConfigurationLoader } from "./ConfigurationLoader"

let currentEnvironment: ApplicationEnvironment | null = null

export const EnvironmentManager = {
  async resolve(envType: string = "development"): Promise<ApplicationEnvironment> {
    const config = await ConfigurationLoader.load(envType)
    const features = Object.entries(config.features).filter(([, v]) => v === "enabled").map(([k]) => k)

    currentEnvironment = {
      type: config.environment,
      name: config.environment,
      deploymentMode: envType === "air_gapped" ? "air-gapped" : "standard",
      runtimeProfile: envType === "production" ? "production" : "development",
      features,
    }
    return currentEnvironment
  },

  async getEnvironment(): Promise<ApplicationEnvironment | null> {
    return currentEnvironment
  },

  async isProduction(): Promise<boolean> {
    return currentEnvironment?.type === "production"
  },

  async isAirGapped(): Promise<boolean> {
    return currentEnvironment?.type === "air_gapped"
  },
}