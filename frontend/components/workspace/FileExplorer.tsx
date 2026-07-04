"use client"

import { useCallback, useRef, useState } from "react"
import type { WorkspaceDocument } from "@/types/workspace"

interface Props {
  wsId: string
  token?: string | null
  documents: WorkspaceDocument[]
  onUploaded: (doc: WorkspaceDocument) => void
  onDeleted: (docId: string) => void
}

const FILE_ICONS: Record<string, string> = {
  pdf: "📄", docx: "📝", txt: "📃", md: "📓",
  pptx: "📊", png: "🖼️", jpg: "🖼️", jpeg: "🖼️",
  gif: "🖼️", webp: "🖼️", bmp: "🖼️", tiff: "🖼️",
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function FileExplorer({ wsId, token, documents, onUploaded, onDeleted }: Props) {
  const [uploading, setUploading]   = useState(false)
  const [progress, setProgress]     = useState(0)
  const [dragOver, setDragOver]     = useState(false)
  const [error, setError]           = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFiles = useCallback(
    async (files: FileList | File[]) => {
      const arr = Array.from(files)
      if (!arr.length) return

      setError(null)
      setUploading(true)
      setProgress(0)

      for (const file of arr) {
        try {
          const { uploadDocument } = await import("@/services/workspaceApi")
          const doc = await uploadDocument(wsId, file, token, setProgress)
          onUploaded(doc)
        } catch (e: unknown) {
          setError(e instanceof Error ? e.message : "Upload failed")
        }
      }

      setUploading(false)
      setProgress(0)
    },
    [wsId, token, onUploaded]
  )

  const handleDelete = async (docId: string) => {
    setDeletingId(docId)
    try {
      const { deleteDocument } = await import("@/services/workspaceApi")
      await deleteDocument(wsId, docId, token)
      onDeleted(docId)
    } catch {
      setError("Delete failed")
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Drop zone */}
      <div
        className={`
          relative border-2 border-dashed rounded-xl p-6 text-center cursor-pointer
          transition-all duration-200
          ${dragOver
            ? "border-[#82c0a4] bg-[#82c0a4]/10"
            : "border-slate-600 hover:border-teal-500 hover:bg-slate-800/50"
          }
        `}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          handleFiles(e.dataTransfer.files)
        }}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          multiple
          accept=".pdf,.docx,.txt,.md,.pptx,.png,.jpg,.jpeg,.gif,.webp"
          onChange={(e) => e.target.files && handleFiles(e.target.files)}
        />
        {uploading ? (
          <div className="flex flex-col items-center gap-2">
            <div className="w-48 h-2 bg-slate-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-[#82c0a4] transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-sm text-[#82c0a4]">Uploading & indexing… {progress}%</p>
          </div>
        ) : (
          <>
            <p className="text-2xl mb-1">📂</p>
            <p className="text-sm text-slate-300 font-medium">
              Drop files here or click to upload
            </p>
            <p className="text-xs text-slate-500 mt-1">
              PDF · DOCX · TXT · MD · PPTX · Images · Max 50 MB
            </p>
          </>
        )}
      </div>

      {error && (
        <div className="text-xs text-red-400 bg-red-950/30 border border-red-800 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      {/* Document list */}
      <div className="flex flex-col gap-1">
        {documents.length === 0 ? (
          <p className="text-xs text-slate-500 text-center py-4">No documents uploaded yet</p>
        ) : (
          documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center gap-3 px-3 py-2 rounded-lg bg-slate-800/60 hover:bg-slate-700/60 group"
            >
              <span className="text-lg flex-shrink-0">
                {FILE_ICONS[doc.file_type] ?? "📄"}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-200 truncate">{doc.filename}</p>
                <p className="text-xs text-slate-500">
                  {doc.total_chunks} chunks · {doc.total_pages} pages · {formatBytes(doc.file_size)}
                </p>
              </div>
              <button
                className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-300 text-xs px-2 py-1 rounded transition-opacity"
                onClick={() => handleDelete(doc.id)}
                disabled={deletingId === doc.id}
                title="Delete document"
              >
                {deletingId === doc.id ? "…" : "✕"}
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
