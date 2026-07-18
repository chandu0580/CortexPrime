export interface RepositoryScan {
  directory: string
  total_files: number
  total_size_bytes: number
  languages: Record<string, number>
  packages: string[]
  modules: string[]
  configs: string[]
  build_systems: string[]
  files: FileEntry[]
  entities: CodeEntity[]
  entity_count: number
  repo_id: string
  scanned_at: string
}

export interface FileEntry {
  path: string
  name: string
  extension: string
  language: string
  size_bytes: number
  directory: string
}

export interface CodeEntity {
  id: string
  entity_type: string
  name: string
  file_path: string
  line_start: number
  line_end: number
  docstring: string
  parent: string
  metadata: Record<string, unknown>
  relationships: CodeRelation[]
}

export interface CodeRelation {
  type: string
  target_id: string
  target_name: string
}

export interface GraphNode {
  id: string
  type: string
  name: string
  file_path: string
  properties: Record<string, unknown>
}

export interface GraphEdge {
  source: string
  target: string
  type: string
  label: string
}

export interface DependencyGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
  node_count: number
  edge_count: number
}

export interface ImpactResult {
  changed_file: string
  risk_score: number
  risk_level: string
  directly_affected_files: string[]
  all_affected_files: string[]
  affected_apis: string[]
  affected_services: string[]
  affected_models: string[]
  affected_tests: string[]
  affected_frontend_components: string[]
  total_affected_entities: number
  total_dependents: number
  analyzed_at: string
}

export const ENTITY_TYPES = [
  "function", "async_function", "class", "interface", "enum",
  "route", "service", "model", "react_component", "hook",
  "struct", "trait", "impl", "method", "config",
] as const

export type EntityType = typeof ENTITY_TYPES[number]
