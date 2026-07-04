import { TestStatus, type ConnectorHealthResult } from "./types"

export const ConnectorHealthValidator = {
  async validateHealthReporting(connector: { health?: Function }): Promise<boolean> {
    return typeof connector.health === "function"
  },

  async validateMetricsReporting(connector: { metrics?: Function }): Promise<boolean> {
    return typeof connector.metrics === "function"
  },

  async validateHeartbeat(health: { lastHeartbeat?: string; status?: string }): Promise<boolean> {
    return health != null
  },

  async validateStatusReporting(health: { status?: string }): Promise<boolean> {
    const validStatuses = ["healthy", "degraded", "unhealthy", "unknown"]
    return health.status != null && validStatuses.includes(health.status)
  },

  async validate(
    connector: { health?: Function; metrics?: Function },
    health: { status?: string; lastHeartbeat?: string },
  ): Promise<ConnectorHealthResult> {
    const errors: string[] = []
    const healthReporting = await this.validateHealthReporting(connector)
    if (!healthReporting) errors.push("health reporting not implemented")

    const metricsReporting = await this.validateMetricsReporting(connector)
    if (!metricsReporting) errors.push("metrics reporting not implemented")

    const heartbeatSupported = await this.validateHeartbeat(health)
    const statusReporting = await this.validateStatusReporting(health)
    if (!statusReporting) errors.push("status reporting invalid")

    const status: TestStatus = errors.length === 0 ? TestStatus.PASSED : TestStatus.FAILED
    return { healthReporting, metricsReporting, heartbeatSupported, statusReporting, status, errors }
  },
}