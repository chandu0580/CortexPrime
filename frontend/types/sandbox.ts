export interface Sandbox {
  sandbox_id: string
  name: string
  repo_url: string
  branch: string
  language: string
  status: string
  isolation_path: string | null
  workspace_id: string
  build_id: string
  executions: ExecutionRecord[]
  artifacts: ArtifactRecord[]
  logs: LogRecord[]
  resource_usage: ResourceUsage
  timing: Record<string, number>
  error: string
  created_at: string
  updated_at: string
  destroyed_at: string
}

export interface ExecutionRecord {
  execution_id: string
  command: string
  exit_code: number
  stdout: string
  stderr: string
  duration_ms: number
  language: string
  artifacts: ArtifactRecord[]
  resource_usage: ResourceUsage
  timestamp: string
}

export interface ArtifactRecord {
  name: string
  path: string
  size_bytes: number
  type: string
  collected_at: string
}

export interface LogRecord {
  type: string
  message: string
  exit_code: number
  timestamp: string
}

export interface ResourceUsage {
  cpu_percent?: { start: number; end: number; peak: number }
  memory_mb?: { start: number; end: number }
  disk_mb?: { start: number; end: number }
  execution_time_ms?: number
  execution_count?: number
  artifact_count?: number
  total_artifact_size_bytes?: number
  total_execution_time_ms?: number
}

export const SANDBOX_STATUSES = [
  "creating", "ready", "running", "paused",
  "executing", "completed", "failed", "destroyed",
] as const

export type SandboxStatus = typeof SANDBOX_STATUSES[number]

export const SUPPORTED_LANGUAGES = [
  "python", "node", "java", "dotnet", "go", "rust", "shell",
] as const

export type SandboxLanguage = typeof SUPPORTED_LANGUAGES[number]
