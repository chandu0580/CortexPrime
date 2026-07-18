export interface ArchitectureProject {
  project_id: string
  name: string
  description: string
  input_text: string
  input_type: string
  industry: string
  status: "created" | "analyzed"
  requirements: Record<string, unknown>
  domain: Record<string, unknown>
  architecture: Record<string, unknown>
  technology: Record<string, unknown>
  database: Record<string, unknown>
  apis: Record<string, unknown>
  events: Record<string, unknown>
  plan: Record<string, unknown>
  decisions: Record<string, unknown>[]
  created_at: string
  updated_at: string
  analyzed_at: string
}

export interface ArchitectureDashboardStats {
  total_projects: number
  analyzed: number
  pending: number
  by_industry: Record<string, number>
  generated_at: string
}
