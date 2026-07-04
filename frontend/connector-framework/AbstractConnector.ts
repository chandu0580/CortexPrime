import type { ConnectorDefinition, ConnectorHealth, ConnectorMetric, ConnectorValidation, ConnectorSnapshot } from "./types"

export abstract class AbstractConnector {
  constructor(protected readonly definition: ConnectorDefinition) {}

  abstract initialize(): Promise<ConnectorDefinition>
  abstract shutdown(): Promise<ConnectorDefinition>
  abstract health(): Promise<ConnectorHealth>
  abstract metrics(): Promise<ConnectorMetric[]>
  abstract validate(): Promise<ConnectorValidation>
  abstract snapshot(): Promise<ConnectorSnapshot>

  getId(): string {
    return this.definition.id
  }

  getName(): string {
    return this.definition.name
  }

  getState(): string {
    return this.definition.state
  }
}
