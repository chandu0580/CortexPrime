import type { ConnectorConfiguration, ConnectorValidation } from "./types"
import { generateId } from "./shared"

const configurations = new Map<string, ConnectorConfiguration[]>()

export const ConnectorConfigurationManager = {
  async registerConfiguration(
    connectorId: string,
    key: string,
    value: unknown,
    sensitive = false
  ): Promise<ConnectorConfiguration> {
    const config: ConnectorConfiguration = {
      id: generateId("config"),
      connectorId,
      key,
      value,
      sensitive,
      updatedAt: new Date().toISOString(),
    }
    const existing = configurations.get(connectorId) ?? []
    existing.push(config)
    configurations.set(connectorId, existing)
    return config
  },

  async updateConfiguration(config: ConnectorConfiguration, value: unknown): Promise<ConnectorConfiguration> {
    const updated: ConnectorConfiguration = {
      ...config,
      value,
      updatedAt: new Date().toISOString(),
    }
    const existing = configurations.get(config.connectorId) ?? []
    const idx = existing.findIndex((c) => c.id === config.id)
    if (idx >= 0) {
      existing[idx] = updated
      configurations.set(config.connectorId, existing)
    }
    return updated
  },

  async validateConfiguration(config: ConnectorConfiguration): Promise<ConnectorValidation> {
    const errors: string[] = []
    const warnings: string[] = []
    if (!config.key) errors.push("configuration key is required")
    if (!config.connectorId) errors.push("connector id is required")
    if (config.sensitive && config.value === undefined) warnings.push("sensitive configuration has no value")
    return {
      id: generateId("val"),
      connectorId: config.connectorId,
      type: "configuration",
      result: errors.length > 0 ? "failed" : warnings.length > 0 ? "warning" : "passed",
      errors,
      warnings,
      details: { key: config.key },
      timestamp: new Date().toISOString(),
    }
  },

  async snapshot(connectorId: string): Promise<ConnectorConfiguration[]> {
    const configs = configurations.get(connectorId) ?? []
    return configs.map((c) => ({
      ...c,
      updatedAt: new Date().toISOString(),
    }))
  },

  async getConfigurations(connectorId: string): Promise<ConnectorConfiguration[]> {
    return configurations.get(connectorId) ?? []
  },
}
