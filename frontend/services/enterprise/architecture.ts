import type { ArchitectureProject, ArchitectureDashboardStats } from "@/types/architecture"

const BASE = "/api/architecture"

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`Architecture API ${res.status}: ${body}`)
  }
  return res.json()
}

export async function listProjects(status = "", limit = 50): Promise<ArchitectureProject[]> {
  const params = new URLSearchParams()
  if (status) params.set("status", status)
  params.set("limit", String(limit))
  return fetchJSON<ArchitectureProject[]>(`${BASE}/projects?${params}`)
}

export async function createProject(name: string, description = "", inputText = "", inputType = "plain_text"): Promise<ArchitectureProject> {
  const params = new URLSearchParams()
  params.set("name", name)
  if (description) params.set("description", description)
  if (inputText) params.set("input_text", inputText)
  params.set("input_type", inputType)
  return fetchJSON<ArchitectureProject>(`${BASE}/projects?${params}`, { method: "POST" })
}

export async function getProject(id: string): Promise<ArchitectureProject> {
  return fetchJSON<ArchitectureProject>(`${BASE}/projects/${id}`)
}

export async function deleteProject(id: string): Promise<void> {
  await fetchJSON(`${BASE}/projects/${id}`, { method: "DELETE" })
}

export async function analyzeProject(name = "", description = "", inputText = ""): Promise<{ status: string; project: ArchitectureProject }> {
  const params = new URLSearchParams()
  if (name) params.set("name", name)
  if (description) params.set("description", description)
  if (inputText) params.set("input_text", inputText)
  return fetchJSON(`${BASE}/analyze?${params}`, { method: "POST" })
}

export async function analyzeExistingProject(id: string): Promise<{ status: string; project: ArchitectureProject }> {
  return fetchJSON(`${BASE}/projects/${id}/analyze`, { method: "POST" })
}

export async function getDomains(projectId: string): Promise<Record<string, unknown>> {
  return fetchJSON(`${BASE}/${projectId}/domains`)
}

export async function getServices(projectId: string): Promise<Record<string, unknown>[]> {
  return fetchJSON(`${BASE}/${projectId}/services`)
}

export async function getDatabase(projectId: string): Promise<Record<string, unknown>> {
  return fetchJSON(`${BASE}/${projectId}/database`)
}

export async function getApis(projectId: string): Promise<Record<string, unknown>> {
  return fetchJSON(`${BASE}/${projectId}/apis`)
}

export async function getEvents(projectId: string): Promise<Record<string, unknown>> {
  return fetchJSON(`${BASE}/${projectId}/events`)
}

export async function getMissions(projectId: string): Promise<Record<string, unknown>[]> {
  return fetchJSON(`${BASE}/${projectId}/missions`)
}

export async function getGraph(projectId: string): Promise<Record<string, unknown>> {
  return fetchJSON(`${BASE}/${projectId}/graph`)
}

export async function getArchitectureDashboard(): Promise<ArchitectureDashboardStats> {
  return fetchJSON<ArchitectureDashboardStats>(`${BASE}/dashboard`)
}
