import neo4j, { Driver, Session, Result } from "neo4j-driver"

export interface Neo4jClientConfig {
  uri: string
  username: string
  password: string
  database?: string
  encrypted?: boolean
  trust?: "TRUST_ALL_CERTIFICATES" | "TRUST_SYSTEM_CA_SIGNED_CERTIFICATES"
  maxConnectionPoolSize?: number
  connectionAcquisitionTimeout?: number
  maxTransactionRetryTime?: number
}

let driver: Driver | null = null
let defaultDatabase: string = "neo4j"

export const Neo4jClient = {
  async connect(config: Neo4jClientConfig): Promise<Driver> {
    if (driver) return driver

    driver = neo4j.driver(
      config.uri,
      neo4j.auth.basic(config.username, config.password),
      {
        encrypted: config.encrypted ?? true,
        trust: config.trust ?? "TRUST_SYSTEM_CA_SIGNED_CERTIFICATES",
        maxConnectionPoolSize: config.maxConnectionPoolSize ?? 100,
        connectionAcquisitionTimeout: config.connectionAcquisitionTimeout ?? 60000,
        maxTransactionRetryTime: config.maxTransactionRetryTime ?? 30000,
      },
    )

    defaultDatabase = config.database ?? "neo4j"
    await driver.verifyConnectivity()
    return driver
  },

  async disconnect(): Promise<void> {
    if (driver) {
      await driver.close()
      driver = null
    }
  },

  getDriver(): Driver | null {
    return driver
  },

  getDatabase(): string {
    return defaultDatabase
  },

  isConnected(): boolean {
    return driver !== null
  },

  async ping(): Promise<boolean> {
    if (!driver) return false
    try {
      const session = driver.session({ database: defaultDatabase })
      try {
        await session.run("RETURN 1 AS result")
        return true
      } finally {
        await session.close()
      }
    } catch {
      return false
    }
  },

  async healthCheck(): Promise<{ connected: boolean; latencyMs: number }> {
    if (!driver) return { connected: false, latencyMs: 0 }
    const start = Date.now()
    try {
      const session = driver.session({ database: defaultDatabase })
      try {
        await session.run("RETURN 1 AS result")
        return { connected: true, latencyMs: Date.now() - start }
      } finally {
        await session.close()
      }
    } catch {
      return { connected: false, latencyMs: Date.now() - start }
    }
  },

  session(database?: string): Session {
    if (!driver) throw new Error("Neo4j driver not connected")
    return driver.session({ database: database ?? defaultDatabase })
  },

  async run(cypher: string, params?: Record<string, unknown>, database?: string): Promise<Result> {
    const session = this.session(database)
    try {
      return await session.run(cypher, params ?? {})
    } finally {
      await session.close()
    }
  },

  async runInTransaction<T>(
    work: (tx: any) => Promise<T>,
    database?: string,
  ): Promise<T> {
    const session = this.session(database)
    try {
      return await session.executeWrite(work)
    } finally {
      await session.close()
    }
  },

  async runInReadTransaction<T>(
    work: (tx: any) => Promise<T>,
    database?: string,
  ): Promise<T> {
    const session = this.session(database)
    try {
      return await session.executeRead(work)
    } finally {
      await session.close()
    }
  },

  async createIndexes(): Promise<void> {
    const indexQueries = [
      "CREATE INDEX entity_id IF NOT EXISTS FOR (e:Entity) ON (e.entityId)",
      "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)",
      "CREATE INDEX entity_category IF NOT EXISTS FOR (e:Entity) ON (e.category)",
      "CREATE INDEX entity_status IF NOT EXISTS FOR (e:Entity) ON (e.status)",
      "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.entityType)",
      "CREATE INDEX node_id IF NOT EXISTS FOR (n:GraphNode) ON (n.nodeId)",
      "CREATE INDEX node_entity IF NOT EXISTS FOR (n:GraphNode) ON (n.entityId)",
      "CREATE INDEX relationship_id IF NOT EXISTS FOR ()-[r:RELATES_TO]-() ON (r.relationshipId)",
      "CREATE INDEX inference_id IF NOT EXISTS FOR (i:Inference) ON (i.inferenceId)",
      "CREATE CONSTRAINT entity_unique IF NOT EXISTS FOR (e:Entity) REQUIRE (e.entityId) IS UNIQUE",
      "CREATE CONSTRAINT node_unique IF NOT EXISTS FOR (n:GraphNode) REQUIRE (n.nodeId) IS UNIQUE",
      "CREATE CONSTRAINT relationship_unique IF NOT EXISTS FOR ()-[r:RELATES_TO]-() REQUIRE (r.relationshipId) IS UNIQUE",
    ]

    for (const query of indexQueries) {
      try {
        await this.run(query)
      } catch {
        // Index may already exist
      }
    }
  },
}
