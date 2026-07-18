import { apiUrl } from "@/lib/constants"

export class ApiError extends Error {
  status: number
  data: unknown

  constructor(status: number, message: string, data?: unknown) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.data = data
  }
}

export interface RequestOptions {
  signal?: AbortSignal
  headers?: Record<string, string>
  params?: Record<string, unknown>
}

function buildUrl(endpoint: string, params?: Record<string, unknown>): string {
  if (!params) return endpoint;
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) usp.set(k, String(v));
  }
  const qs = usp.toString();
  return qs ? `${endpoint}?${qs}` : endpoint;
}

async function request<T = unknown>(
  endpoint: string,
  method = "GET",
  body?: unknown,
  options?: RequestOptions,
): Promise<T> {
  const url = buildUrl(endpoint, options?.params);
  const res = await fetch(apiUrl(url), {
    method,
    headers: { "Content-Type": "application/json", ...options?.headers },
    credentials: "include",
    signal: options?.signal,
    body: body != null ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    let detail = `API ${method} ${endpoint} \u2192 ${res.status}`
    let data: unknown
    try {
      data = await res.json()
      if (data && typeof data === "object" && "detail" in (data as Record<string, unknown>)) {
        detail = (data as Record<string, string>).detail
      }
    } catch {
      // response body not JSON — use default detail message
    }
    throw new ApiError(res.status, detail, data)
  }

  // Handle 204 No Content
  if (res.status === 204) return undefined as T

  return res.json() as Promise<T>
}

export const api = {
  get:     <T>(path: string, opts?: RequestOptions) => request<T>(path, "GET", undefined, opts),
  post:    <T>(path: string, body?: unknown, opts?: RequestOptions) => request<T>(path, "POST", body, opts),
  put:     <T>(path: string, body?: unknown, opts?: RequestOptions) => request<T>(path, "PUT", body, opts),
  delete:  <T>(path: string, opts?: RequestOptions) => request<T>(path, "DELETE", undefined, opts),
}
