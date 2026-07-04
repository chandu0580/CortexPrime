import { FeatureFlagState, type ApplicationConfiguration, type ApplicationEnvironmentType } from "./types"
import { generateId } from "./shared"

const configProfiles: Record<string, ApplicationConfiguration> = {
  development: {
    id: generateId("config"),
    environment: "development" as ApplicationEnvironmentType,
    version: "1.0.0",
    features: { voice: FeatureFlagState.ENABLED, browser: FeatureFlagState.ENABLED, connectors: FeatureFlagState.ENABLED, analytics: FeatureFlagState.ENABLED, governance: FeatureFlagState.DISABLED, observability: FeatureFlagState.ENABLED },
    settings: {
      logLevel: "debug",
      telemetry: false,
      llmProviders: [
        { type: "ollama", model: "llama3", endpoint: "http://localhost:11434", maxTokens: 4096, temperature: 0.3, timeoutMs: 120000 },
      ],
    },
    loadedAt: new Date().toISOString(),
  },
  testing: {
    id: generateId("config"),
    environment: "testing" as ApplicationEnvironmentType,
    version: "1.0.0",
    features: { voice: FeatureFlagState.DISABLED, browser: FeatureFlagState.ENABLED, connectors: FeatureFlagState.DISABLED, analytics: FeatureFlagState.DISABLED, governance: FeatureFlagState.DISABLED, observability: FeatureFlagState.ENABLED },
    settings: {
      logLevel: "debug",
      telemetry: false,
      llmProviders: [
        { type: "ollama", model: "llama3", endpoint: "http://localhost:11434", maxTokens: 4096, temperature: 0.3, timeoutMs: 120000 },
      ],
    },
    loadedAt: new Date().toISOString(),
  },
  staging: {
    id: generateId("config"),
    environment: "staging" as ApplicationEnvironmentType,
    version: "1.0.0",
    features: { voice: FeatureFlagState.ENABLED, browser: FeatureFlagState.ENABLED, connectors: FeatureFlagState.ENABLED, analytics: FeatureFlagState.ENABLED, governance: FeatureFlagState.ENABLED, observability: FeatureFlagState.ENABLED },
    settings: {
      logLevel: "info",
      telemetry: true,
      llmProviders: [
        { type: "openai", model: "gpt-4o", maxTokens: 4096, temperature: 0.3, timeoutMs: 60000 },
        { type: "anthropic", model: "claude-3-5-sonnet-20241022", maxTokens: 4096, temperature: 0.3, timeoutMs: 60000 },
        { type: "azure-openai", model: "gpt-4o", deploymentName: "gpt-4o", apiVersion: "2024-02-01", maxTokens: 4096, temperature: 0.3, timeoutMs: 60000 },
        { type: "gemini", model: "gemini-1.5-pro", maxTokens: 4096, temperature: 0.3, timeoutMs: 60000 },
      ],
    },
    loadedAt: new Date().toISOString(),
  },
  production: {
    id: generateId("config"),
    environment: "production" as ApplicationEnvironmentType,
    version: "1.0.0",
    features: { voice: FeatureFlagState.ENABLED, browser: FeatureFlagState.ENABLED, connectors: FeatureFlagState.ENABLED, analytics: FeatureFlagState.ENABLED, governance: FeatureFlagState.ENABLED, observability: FeatureFlagState.ENABLED },
    settings: {
      logLevel: "warn",
      telemetry: true,
      llmProviders: [
        { type: "openai", model: "gpt-4o", maxTokens: 4096, temperature: 0.3, timeoutMs: 60000 },
        { type: "anthropic", model: "claude-3-5-sonnet-20241022", maxTokens: 4096, temperature: 0.3, timeoutMs: 60000 },
        { type: "azure-openai", model: "gpt-4o", deploymentName: "gpt-4o", apiVersion: "2024-02-01", maxTokens: 4096, temperature: 0.3, timeoutMs: 60000 },
        { type: "gemini", model: "gemini-1.5-pro", maxTokens: 4096, temperature: 0.3, timeoutMs: 60000 },
      ],
    },
    loadedAt: new Date().toISOString(),
  },
  "air-gapped": {
    id: generateId("config"),
    environment: "air_gapped" as ApplicationEnvironmentType,
    version: "1.0.0",
    features: { voice: FeatureFlagState.DISABLED, browser: FeatureFlagState.DISABLED, connectors: FeatureFlagState.DISABLED, analytics: FeatureFlagState.ENABLED, governance: FeatureFlagState.ENABLED, observability: FeatureFlagState.ENABLED },
    settings: {
      logLevel: "warn",
      telemetry: false,
      networkBlocked: true,
      llmProviders: [
        { type: "ollama", model: "llama3", endpoint: "http://localhost:11434", maxTokens: 4096, temperature: 0.3, timeoutMs: 120000 },
      ],
    },
    loadedAt: new Date().toISOString(),
  },
}

let currentConfig: ApplicationConfiguration | null = null

export const ConfigurationLoader = {
  async load(environment: string = "development"): Promise<ApplicationConfiguration> {
    const profile = configProfiles[environment] ?? configProfiles.development
    currentConfig = { ...profile, id: generateId("config"), loadedAt: new Date().toISOString() }
    return currentConfig
  },

  async getConfig(): Promise<ApplicationConfiguration | null> {
    return currentConfig
  },

  async getSetting(key: string): Promise<unknown | null> {
    return currentConfig?.settings[key] ?? null
  },
}