import { FeatureFlagState, type ApplicationFeature } from "./types"
import { generateId } from "./shared"

const featureFlags = new Map<string, ApplicationFeature>()

export const FeatureFlagManager = {
  async register(name: string, description: string, initialState: FeatureFlagState = FeatureFlagState.DISABLED): Promise<ApplicationFeature> {
    const feature: ApplicationFeature = { id: generateId("feature"), name, description, state: initialState }
    featureFlags.set(name, feature)
    return feature
  },

  async enable(name: string): Promise<ApplicationFeature | null> {
    const feature = featureFlags.get(name)
    if (!feature) return null
    const updated: ApplicationFeature = { ...feature, state: FeatureFlagState.ENABLED }
    featureFlags.set(name, updated)
    return updated
  },

  async disable(name: string): Promise<ApplicationFeature | null> {
    const feature = featureFlags.get(name)
    if (!feature) return null
    const updated: ApplicationFeature = { ...feature, state: FeatureFlagState.DISABLED }
    featureFlags.set(name, updated)
    return updated
  },

  async isEnabled(name: string): Promise<boolean> {
    return featureFlags.get(name)?.state === FeatureFlagState.ENABLED
  },

  async listFeatures(): Promise<ApplicationFeature[]> {
    return Array.from(featureFlags.values())
  },

  async validate(name: string): Promise<boolean> {
    return featureFlags.has(name)
  },

  async loadFromConfig(features: Record<string, FeatureFlagState>): Promise<void> {
    for (const [name, state] of Object.entries(features)) {
      if (featureFlags.has(name)) {
        await (state === FeatureFlagState.ENABLED ? this.enable(name) : this.disable(name))
      } else {
        await this.register(name, `Feature: ${name}`, state)
      }
    }
  },
}