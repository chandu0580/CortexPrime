import Redis from "ioredis"

export interface RedisClientConfig {
  host: string
  port: number
  password?: string
  db?: number
  keyPrefix?: string
  connectTimeout?: number
  maxRetriesPerRequest?: number
  retryStrategy?: (times: number) => number | null
}

let client: Redis | null = null

export const RedisClient = {
  async connect(config?: RedisClientConfig): Promise<Redis> {
    if (client) return client

    client = new Redis({
      host: config?.host ?? "127.0.0.1",
      port: config?.port ?? 6379,
      password: config?.password,
      db: config?.db ?? 0,
      keyPrefix: config?.keyPrefix ?? "mem:",
      connectTimeout: config?.connectTimeout ?? 5000,
      maxRetriesPerRequest: config?.maxRetriesPerRequest ?? 3,
      retryStrategy: config?.retryStrategy ?? ((times: number) => {
        if (times > 10) return null
        return Math.min(times * 200, 5000)
      }),
      lazyConnect: true,
    })

    await client.connect()
    return client
  },

  async disconnect(): Promise<void> {
    if (client) {
      await client.quit()
      client = null
    }
  },

  getClient(): Redis | null {
    return client
  },

  isConnected(): boolean {
    return client !== null && client.status === "ready"
  },

  async ping(): Promise<boolean> {
    if (!client) return false
    try {
      const result = await client.ping()
      return result === "PONG"
    } catch {
      return false
    }
  },

  async healthCheck(): Promise<{ connected: boolean; latencyMs: number }> {
    if (!client) return { connected: false, latencyMs: 0 }
    const start = Date.now()
    try {
      await client.ping()
      return { connected: true, latencyMs: Date.now() - start }
    } catch {
      return { connected: false, latencyMs: Date.now() - start }
    }
  },

  async flushPrefix(prefix: string): Promise<void> {
    if (!client) return
    const keys = await client.keys(`${prefix}*`)
    if (keys.length > 0) {
      await client.del(...keys)
    }
  },
}
