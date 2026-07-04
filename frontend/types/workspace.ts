// Workspace Intelligence — TypeScript types

export interface Workspace {
  id: string
  name: string
  description: string
  created_at: string
  metadata: Record<string, unknown>
  doc_count: number
}

export interface WorkspaceDocument {
  id: string
  workspace_id: string
  filename: string
  file_type: string
  content_hash: string
  total_chunks: number
  total_pages: number
  file_size: number
  created_at: string
  metadata: Record<string, unknown>
}

export interface DocumentChunk {
  id: string
  chunk_index: number
  content: string
  page_number: number | null
  char_start: number
  char_end: number
  metadata: Record<string, unknown>
}

export interface RetrievedChunk {
  chunk_id: string
  document_id: string
  workspace_id: string
  filename: string
  page_number: number | null
  content: string
  score: number
  chunk_index: number
}

export interface Citation {
  citation_id: string
  filename: string
  page_number: number | null
  chunk_index: number
  excerpt: string
  score: number
  document_id: string
}

export interface WorkspaceChatResponse {
  answer: string
  citations: Citation[]
  chunks_used: number
  model_used: string
}

export interface SearchResult {
  chunks: RetrievedChunk[]
  citations: Citation[]
  count: number
}
