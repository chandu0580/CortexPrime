import type { ConnectorDefinition, ConnectorCapability, ConnectorConfiguration, ConnectorValidation, ConnectorPermission, ConnectorValidationResult } from "./types"
import { generateId } from "./shared"

export const ConnectorValidator = {
  async validateLifecycle(definition: ConnectorDefinition): Promise<ConnectorValidation> {
    const errors: string[] = []
    if (!definition.id) errors.push("connector id is required")
    if (!definition.state) errors.push("connector state is required")
    return createValidation(definition.id, "lifecycle", errors)
  },

  async validateCapabilityIntegrity(capabilities: ConnectorCapability[]): Promise<ConnectorValidation> {
    const errors: string[] = []
    for (const cap of capabilities) {
      if (!cap.id) errors.push("capability missing id")
      if (!cap.name) errors.push("capability missing name")
      if (!cap.version) errors.push("capability missing version")
    }
    return createValidation("", "capability_integrity", errors)
  },

  async validateConfigurationIntegrity(configurations: ConnectorConfiguration[]): Promise<ConnectorValidation> {
    const errors: string[] = []
    for (const config of configurations) {
      if (!config.key) errors.push("configuration missing key")
      if (!config.connectorId) errors.push("configuration missing connector id")
    }
    return createValidation("", "configuration_integrity", errors)
  },

  async validateMetadata(definition: ConnectorDefinition): Promise<ConnectorValidation> {
    const errors: string[] = []
    if (!definition.identity.name) errors.push("connector name is required")
    if (!definition.identity.version) errors.push("connector version is required")
    if (!definition.identity.vendor) errors.push("connector vendor is required")
    return createValidation(definition.id, "metadata", errors)
  },

  async validatePermissions(permissions: ConnectorPermission[]): Promise<ConnectorValidation> {
    const errors: string[] = []
    for (const perm of permissions) {
      if (!perm.resource) errors.push("permission missing resource")
      if (!perm.level) errors.push("permission missing level")
    }
    return createValidation("", "permissions", errors)
  },
}

async function createValidation(
  connectorId: string,
  type: string,
  errors: string[]
): Promise<ConnectorValidation> {
  const result: ConnectorValidationResult = errors.length > 0 ? "failed" : "passed"
  return {
    id: generateId("val"),
    connectorId,
    type,
    result,
    errors,
    warnings: [],
    details: {},
    timestamp: new Date().toISOString(),
  }
}
