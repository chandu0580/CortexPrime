import type { ProviderConfig, ProviderType, LLMResponse, StreamingChunk, TokenUsage, ModelCapability } from "./types"
import { ReasoningMetricsCollector } from "./reasoning-metrics"

const providerConfigs = new Map<string, ProviderConfig>()
const circuitBreakers = new Map<string, { failures: number; lastFailure: number; open: boolean }>()

function calculateCost(type: ProviderType, tokens: TokenUsage): number {
  const rates: Record<string, { prompt: number; completion: number }> = {
    openai: { prompt: 0.00001, completion: 0.00003 },
    "azure-openai": { prompt: 0.00001, completion: 0.00003 },
    anthropic: { prompt: 0.000015, completion: 0.000075 },
    gemini: { prompt: 0.000005, completion: 0.000015 },
    ollama: { prompt: 0, completion: 0 },
  }
  const rate = rates[type] ?? rates.openai
  return (tokens.prompt * rate.prompt) + (tokens.completion * rate.completion)
}

function checkCircuitBreaker(providerId: string): boolean {
  const cb = circuitBreakers.get(providerId)
  if (!cb || !cb.open) return true

  const cooldownMs = 60000
  if (Date.now() - cb.lastFailure > cooldownMs) {
    cb.open = false
    cb.failures = 0
    return true
  }
  return false
}

function recordFailure(providerId: string): void {
  const cb = circuitBreakers.get(providerId) ?? { failures: 0, lastFailure: 0, open: false }
  cb.failures++
  cb.lastFailure = Date.now()
  if (cb.failures >= 3) cb.open = true
  circuitBreakers.set(providerId, cb)
}

function recordSuccess(providerId: string): void {
  const cb = circuitBreakers.get(providerId)
  if (cb) {
    cb.failures = 0
    cb.open = false
  }
}

function buildHeaders(config: ProviderConfig): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" }
  if (config.apiKey) {
    if (config.type === "anthropic") {
      headers["x-api-key"] = config.apiKey
      headers["anthropic-version"] = "2023-06-01"
    } else {
      headers["Authorization"] = `Bearer ${config.apiKey}`
    }
  }
  return headers
}

async function handleResponse(res: Response, providerId: string): Promise<unknown> {
  if (!res.ok) {
    const errText = await res.text().catch(() => "unknown error")
    recordFailure(providerId)
    throw new Error(`HTTP ${res.status} from ${providerId}: ${errText}`)
  }
  recordSuccess(providerId)
  return res.json()
}

function extractTokens(data: Record<string, unknown>, type: ProviderType): TokenUsage {
  if (type === "anthropic") {
    const input = (data as { usage?: { input_tokens: number; output_tokens: number } }).usage
    return input
      ? { prompt: input.input_tokens, completion: input.output_tokens, total: input.input_tokens + input.output_tokens }
      : { prompt: 0, completion: 0, total: 0 }
  }
  if (type === "gemini") {
    const usage = (data as { usageMetadata?: { promptTokenCount: number; candidatesTokenCount: number } }).usageMetadata
    return usage
      ? { prompt: usage.promptTokenCount, completion: usage.candidatesTokenCount, total: usage.promptTokenCount + usage.candidatesTokenCount }
      : { prompt: 0, completion: 0, total: 0 }
  }
  const usage = (data as { usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number } }).usage
  return usage
    ? { prompt: usage.prompt_tokens, completion: usage.completion_tokens, total: usage.total_tokens }
    : { prompt: 0, completion: 0, total: 0 }
}

export const LLMProviderRegistry = {
  configs: providerConfigs,

  async register(config: ProviderConfig): Promise<void> {
    const id = `${config.type}:${config.model}`
    providerConfigs.set(id, config)
    circuitBreakers.set(id, { failures: 0, lastFailure: 0, open: false })
  },

  async unregister(providerId: string): Promise<void> {
    providerConfigs.delete(providerId)
    circuitBreakers.delete(providerId)
  },

  async getConfig(providerId: string): Promise<ProviderConfig | null> {
    return providerConfigs.get(providerId) ?? null
  },

  async listProviders(): Promise<ProviderConfig[]> {
    return Array.from(providerConfigs.values())
  },

  async isAvailable(providerId: string): Promise<boolean> {
    const config = providerConfigs.get(providerId)
    if (!config) return false
    return checkCircuitBreaker(providerId)
  },

  async selectForCapability(capability: ModelCapability, preferredType?: ProviderType): Promise<ProviderConfig | null> {
    const candidates = Array.from(providerConfigs.values())
    const available = candidates.filter((c) => {
      const id = `${c.type}:${c.model}`
      return checkCircuitBreaker(id)
    })

    if (preferredType) {
      const preferred = available.find((c) => c.type === preferredType)
      if (preferred) return preferred
    }

    return available[0] ?? null
  },

  async generate(config: ProviderConfig, prompt: string, structured: boolean): Promise<LLMResponse> {
    const startTime = Date.now()
    const providerId = `${config.type}:${config.model}`

    if (!checkCircuitBreaker(providerId)) {
      throw new Error(`Circuit breaker open for ${providerId}`)
    }

    let data: Record<string, unknown>
    let content: string

    switch (config.type) {
      case "openai":
        data = await this.callOpenAI(config, prompt)
        content = (data as { choices: Array<{ message: { content: string } }> }).choices[0]?.message?.content ?? ""
        break
      case "azure-openai":
        data = await this.callAzureOpenAI(config, prompt)
        content = (data as { choices: Array<{ message: { content: string } }> }).choices[0]?.message?.content ?? ""
        break
      case "anthropic":
        data = await this.callAnthropic(config, prompt)
        content = (data as { content: Array<{ text: string }> }).content[0]?.text ?? ""
        break
      case "gemini":
        data = await this.callGemini(config, prompt)
        content = (data as { candidates: Array<{ content: { parts: Array<{ text: string }> } }> }).candidates[0]?.content?.parts[0]?.text ?? ""
        break
      case "ollama":
        data = await this.callOllama(config, prompt)
        content = (data as { response: string }).response ?? ""
        break
      default:
        throw new Error(`Unsupported provider type: ${config.type}`)
    }

    const latencyMs = Date.now() - startTime
    const tokens = extractTokens(data, config.type)
    const cost = calculateCost(config.type, tokens)

    await ReasoningMetricsCollector.recordRequest(config.type, tokens, latencyMs, cost, true)

    return {
      content,
      structured: null,
      tokensUsed: tokens,
      latencyMs,
      provider: config.type,
      model: config.model,
      finishReason: "stop",
      timestamp: new Date().toISOString(),
    }
  },

  async stream(config: ProviderConfig, prompt: string, onChunk: (chunk: StreamingChunk) => void, signal?: AbortSignal): Promise<LLMResponse> {
    const startTime = Date.now()
    const providerId = `${config.type}:${config.model}`
    let fullContent = ""
    const promptTokens = 0
    let completionTokens = 0

    if (!checkCircuitBreaker(providerId)) {
      throw new Error(`Circuit breaker open for ${providerId}`)
    }

    const body: Record<string, unknown> = {
      model: config.model,
      messages: [{ role: "user", content: prompt }],
      stream: true,
      max_tokens: config.maxTokens ?? 4096,
      temperature: config.temperature ?? 0.3,
    }

    if (config.type === "anthropic") {
      const anthropicBody = {
        model: config.model,
        max_tokens: config.maxTokens ?? 4096,
        messages: [{ role: "user", content: prompt }],
        stream: true,
      }

      try {
        const res = await fetch(config.endpoint ?? "https://api.anthropic.com/v1/messages", {
          method: "POST",
          headers: buildHeaders(config),
          body: JSON.stringify(anthropicBody),
          signal,
        })

        if (!res.ok) {
          recordFailure(providerId)
          throw new Error(`Anthropic HTTP ${res.status}`)
        }

        const reader = res.body?.getReader()
        if (!reader) throw new Error("No response body for streaming")

        const decoder = new TextDecoder()
        let buffer = ""

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split("\n")
          buffer = lines.pop() ?? ""

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue
            const jsonStr = line.slice(6).trim()
            if (!jsonStr || jsonStr === "[DONE]") continue

            const chunk = JSON.parse(jsonStr) as Record<string, unknown>
            if (chunk.type === "content_block_delta") {
              const delta = chunk.delta as { text?: string } | undefined
              if (delta?.text) {
                fullContent += delta.text
                completionTokens++
                onChunk({ content: delta.text, done: false, tokensUsed: null, error: null })
              }
            }
          }
        }

        recordSuccess(providerId)
        const tokens: TokenUsage = { prompt: promptTokens, completion: completionTokens, total: promptTokens + completionTokens }
        const latencyMs = Date.now() - startTime
        const cost = calculateCost(config.type, tokens)

        await ReasoningMetricsCollector.recordRequest(config.type, tokens, latencyMs, cost, true)

        onChunk({ content: "", done: true, tokensUsed: tokens, error: null })

        return {
          content: fullContent,
          structured: null,
          tokensUsed: tokens,
          latencyMs,
          provider: config.type,
          model: config.model,
          finishReason: "stop",
          timestamp: new Date().toISOString(),
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          onChunk({ content: "", done: true, tokensUsed: null, error: "cancelled" })
          return {
            content: fullContent, structured: null,
            tokensUsed: { prompt: 0, completion: 0, total: 0 }, latencyMs: Date.now() - startTime,
            provider: config.type, model: config.model, finishReason: "cancelled", timestamp: new Date().toISOString(),
          }
        }
        recordFailure(providerId)
        onChunk({ content: "", done: true, tokensUsed: null, error: (err as Error).message })
        throw err
      }
    }

    const endpoint = this.getEndpoint(config, "/chat/completions")
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: buildHeaders(config),
        body: JSON.stringify(body),
        signal,
      })

      if (!res.ok) {
        recordFailure(providerId)
        throw new Error(`HTTP ${res.status} from ${providerId}`)
      }

      const reader = res.body?.getReader()
      if (!reader) throw new Error("No response body for streaming")

      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() ?? ""

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue
          const jsonStr = line.slice(6).trim()
          if (!jsonStr || jsonStr === "[DONE]") continue

          const chunk = JSON.parse(jsonStr) as Record<string, unknown>
          const delta = (chunk as { choices?: Array<{ delta: { content?: string } }> }).choices?.[0]?.delta?.content
          if (delta) {
            fullContent += delta
            completionTokens++
            onChunk({ content: delta, done: false, tokensUsed: null, error: null })
          }
        }
      }

      recordSuccess(providerId)
      const tokens: TokenUsage = { prompt: promptTokens, completion: completionTokens, total: promptTokens + completionTokens }
      const latencyMs = Date.now() - startTime
      const cost = calculateCost(config.type, tokens)

      await ReasoningMetricsCollector.recordRequest(config.type, tokens, latencyMs, cost, true)

      onChunk({ content: "", done: true, tokensUsed: tokens, error: null })

      return {
        content: fullContent,
        structured: null,
        tokensUsed: tokens,
        latencyMs,
        provider: config.type,
        model: config.model,
        finishReason: "stop",
        timestamp: new Date().toISOString(),
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        onChunk({ content: "", done: true, tokensUsed: null, error: "cancelled" })
        return {
          content: fullContent, structured: null,
          tokensUsed: { prompt: 0, completion: 0, total: 0 }, latencyMs: Date.now() - startTime,
          provider: config.type, model: config.model, finishReason: "cancelled", timestamp: new Date().toISOString(),
        }
      }
      recordFailure(providerId)
      onChunk({ content: "", done: true, tokensUsed: null, error: (err as Error).message })
      throw err
    }
  },

  async getAvailability(): Promise<Record<string, boolean>> {
    const result: Record<string, boolean> = {}
    for (const [id] of providerConfigs) {
      result[id] = checkCircuitBreaker(id)
    }
    return result
  },

  async resetCircuitBreaker(providerId: string): Promise<void> {
    const cb = circuitBreakers.get(providerId)
    if (cb) {
      cb.failures = 0
      cb.open = false
    }
  },

  async callOpenAI(config: ProviderConfig, prompt: string): Promise<Record<string, unknown>> {
    const endpoint = config.endpoint ?? "https://api.openai.com/v1/chat/completions"
    const body = {
      model: config.model,
      messages: [{ role: "user", content: prompt }],
      max_tokens: config.maxTokens ?? 4096,
      temperature: config.temperature ?? 0.3,
      response_format: { type: "json_object" },
    }

    const res = await fetch(endpoint, {
      method: "POST",
      headers: buildHeaders(config),
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(config.timeoutMs ?? 60000),
    })

    return handleResponse(res, `openai:${config.model}`) as Promise<Record<string, unknown>>
  },

  async callAzureOpenAI(config: ProviderConfig, prompt: string): Promise<Record<string, unknown>> {
    const base = config.endpoint ?? "https://api.openai.com/v1"
    const deployment = config.deploymentName ?? config.model
    const apiVersion = config.apiVersion ?? "2024-02-01"
    const endpoint = `${base}/openai/deployments/${deployment}/chat/completions?api-version=${apiVersion}`

    const body = {
      messages: [{ role: "user", content: prompt }],
      max_tokens: config.maxTokens ?? 4096,
      temperature: config.temperature ?? 0.3,
      response_format: { type: "json_object" },
    }

    const res = await fetch(endpoint, {
      method: "POST",
      headers: buildHeaders(config),
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(config.timeoutMs ?? 60000),
    })

    return handleResponse(res, `azure-openai:${config.model}`) as Promise<Record<string, unknown>>
  },

  async callAnthropic(config: ProviderConfig, prompt: string): Promise<Record<string, unknown>> {
    const endpoint = config.endpoint ?? "https://api.anthropic.com/v1/messages"
    const body = {
      model: config.model,
      max_tokens: config.maxTokens ?? 4096,
      messages: [{ role: "user", content: prompt }],
    }

    const res = await fetch(endpoint, {
      method: "POST",
      headers: buildHeaders(config),
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(config.timeoutMs ?? 60000),
    })

    return handleResponse(res, `anthropic:${config.model}`) as Promise<Record<string, unknown>>
  },

  async callGemini(config: ProviderConfig, prompt: string,): Promise<Record<string, unknown>> {
    const apiKey = config.apiKey ?? ""
    const endpoint = `${config.endpoint ?? "https://generativelanguage.googleapis.com/v1beta"}/models/${config.model}:generateContent?key=${apiKey}`
    const body = {
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: {
        maxOutputTokens: config.maxTokens ?? 4096,
        temperature: config.temperature ?? 0.3,
      },
    }

    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(config.timeoutMs ?? 60000),
    })

    return handleResponse(res, `gemini:${config.model}`) as Promise<Record<string, unknown>>
  },

  async callOllama(config: ProviderConfig, prompt: string): Promise<Record<string, unknown>> {
    const endpoint = `${config.endpoint ?? "http://localhost:11434"}/api/generate`
    const body = {
      model: config.model,
      prompt,
      options: {
        num_predict: config.maxTokens ?? 4096,
        temperature: config.temperature ?? 0.3,
      },
      stream: false,
    }

    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(config.timeoutMs ?? 120000),
    })

    return handleResponse(res, `ollama:${config.model}`) as Promise<Record<string, unknown>>
  },

  getEndpoint(config: ProviderConfig, path: string): string {
    const baseMap: Record<string, string> = {
      openai: "https://api.openai.com/v1",
      "azure-openai": config.endpoint ?? "https://api.openai.com/v1",
      gemini: config.endpoint ?? "https://generativelanguage.googleapis.com/v1beta",
      ollama: config.endpoint ?? "http://localhost:11434",
      anthropic: "https://api.anthropic.com/v1",
    }
    const base = baseMap[config.type] ?? baseMap.openai
    return `${base}${path}`
  },
}
