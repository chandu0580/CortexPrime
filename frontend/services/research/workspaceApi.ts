// Workspace Intelligence API client

import type {
  Citation,
  DocumentChunk,
  SearchResult,
  Workspace,
  WorkspaceChatResponse,
  WorkspaceDocument,
} from "@/types/workspace"
import { apiUrl } from "@/lib/constants"

function getHeaders(): HeadersInit {
  return { "Content-Type": "application/json" }
}

// ─────────────────────────────────────────────────────────────────────────────
// WORKSPACE CRUD
// ─────────────────────────────────────────────────────────────────────────────

export async function listWorkspaces(token?: string | null): Promise<Workspace[]> {
  const res = await fetch(apiUrl("/api/workspace/"), {
    headers: getHeaders(),
    credentials: "include",
  })
  if (!res.ok) throw new Error(`Failed to list workspaces: ${res.status}`)
  return res.json()
}

export async function createWorkspace(
  name: string,
  description: string,
  token?: string | null
): Promise<Workspace> {
  const res = await fetch(apiUrl("/api/workspace/"), {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ name, description }),
    credentials: "include",
  })
  if (!res.ok) throw new Error(`Failed to create workspace: ${res.status}`)
  return res.json()
}

export async function deleteWorkspace(wsId: string, token?: string | null): Promise<void> {
  await fetch(apiUrl(`/api/workspace/${wsId}`), {
    method: "DELETE",
    headers: getHeaders(),
    credentials: "include",
  })
}

// ─────────────────────────────────────────────────────────────────────────────
// DOCUMENTS
// ─────────────────────────────────────────────────────────────────────────────

export async function listDocuments(
  wsId: string,
  token?: string | null
): Promise<WorkspaceDocument[]> {
  const res = await fetch(apiUrl(`/api/workspace/${wsId}/documents`), {
    headers: getHeaders(),
    credentials: "include",
  })
  if (!res.ok) throw new Error(`Failed to list documents: ${res.status}`)
  return res.json()
}

export async function uploadDocument(
  wsId: string,
  file: File,
  token?: string | null,
  onProgress?: (pct: number) => void
): Promise<WorkspaceDocument & { message: string }> {
  const form = new FormData()
  form.append("file", file)

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open("POST", apiUrl(`/api/workspace/${wsId}/upload`))
    xhr.withCredentials = true

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText))
        } catch {
          reject(new Error("Invalid response from server"))
        }
      } else {
        try {
          const err = JSON.parse(xhr.responseText)
          reject(new Error(err.detail ?? `Upload failed: ${xhr.status}`))
        } catch {
          reject(new Error(`Upload failed: ${xhr.status}`))
        }
      }
    }

    xhr.onerror = () => reject(new Error("Network error during upload"))
    xhr.send(form)
  })
}

export async function deleteDocument(
  wsId: string,
  docId: string,
  token?: string | null
): Promise<void> {
  await fetch(apiUrl(`/api/workspace/${wsId}/documents/${docId}`), {
    method: "DELETE",
    headers: getHeaders(),
    credentials: "include",
  })
}

export async function getDocumentChunks(
  wsId: string,
  docId: string,
  token?: string | null
): Promise<DocumentChunk[]> {
  const res = await fetch(apiUrl(`/api/workspace/${wsId}/documents/${docId}/chunks`), {
    headers: getHeaders(),
    credentials: "include",
  })
  if (!res.ok) throw new Error(`Failed to get chunks: ${res.status}`)
  return res.json()
}

// ─────────────────────────────────────────────────────────────────────────────
// SEARCH + CHAT
// ─────────────────────────────────────────────────────────────────────────────

export async function searchWorkspace(
  wsId: string,
  query: string,
  nChunks = 8,
  token?: string | null
): Promise<SearchResult> {
  const res = await fetch(apiUrl(`/api/workspace/${wsId}/search`), {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ query, n_chunks: nChunks }),
    credentials: "include",
  })
  if (!res.ok) throw new Error(`Search failed: ${res.status}`)
  return res.json()
}

export async function workspaceChat(
  wsId: string,
  query: string,
  nChunks = 6,
  token?: string | null
): Promise<WorkspaceChatResponse> {
  const res = await fetch(apiUrl(`/api/workspace/${wsId}/chat`), {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ query, workspace_id: wsId, n_chunks: nChunks }),
    credentials: "include",
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `Chat failed: ${res.status}` }))
    throw new Error(err.detail ?? `Chat failed: ${res.status}`)
  }
  return res.json()
}
