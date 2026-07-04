"use client"

import { useState } from "react"
import type { RetrievedChunk, SearchResult } from "@/types/workspace"

interface Props {
  wsId: string
  token?: string | null
  disabled?: boolean
}

export function DocumentSearch({ wsId, token, disabled }: Props) {
  const [query, setQuery]       = useState("")
  const [result, setResult]     = useState<SearchResult | null>(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  const search = async () => {
    if (!query.trim() || loading || disabled) return
    setLoading(true)
    setError(null)
    try {
      const { searchWorkspace } = await import("@/services/workspaceApi")
      const res = await searchWorkspace(wsId, query, 8, token)
      setResult(res)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Search failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Search bar */}
      <div className="flex gap-2">
        <input
          type="text"
          className={`flex-1 bg-slate-800/60 border border-slate-600 rounded-xl px-4 py-2.5
            text-sm text-slate-200 placeholder-slate-500 outline-none focus:border-teal-500
            transition-colors ${disabled ? "opacity-50" : ""}`}
          placeholder={disabled ? "Upload documents first…" : "Search across documents…"}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          disabled={disabled || loading}
        />
        <button
          onClick={search}
          disabled={!query.trim() || loading || disabled}
          className="px-4 py-2 bg-[#4a8c70] hover:bg-[#4a8c70] disabled:opacity-40 rounded-xl
            text-white text-sm font-medium transition-colors flex-shrink-0"
        >
          {loading ? "…" : "Search"}
        </button>
      </div>

      {error && (
        <p className="text-xs text-red-400">{error}</p>
      )}

      {/* Results */}
      {result && (
        <div className="flex flex-col gap-2">
          <p className="text-xs text-slate-500">
            {result.count} chunk{result.count !== 1 ? "s" : ""} found
          </p>
          {result.chunks.map((chunk: RetrievedChunk) => (
            <div
              key={chunk.chunk_id}
              className="border border-slate-700 rounded-lg overflow-hidden bg-slate-800/40
                cursor-pointer hover:border-slate-600 transition-colors"
              onClick={() =>
                setExpanded(expanded === chunk.chunk_id ? null : chunk.chunk_id)
              }
            >
              <div className="flex items-center gap-3 px-3 py-2">
                <span className="text-xs font-medium text-[#4a8c70] flex-shrink-0">
                  {Math.round(chunk.score * 100)}%
                </span>
                <span className="text-xs text-slate-300 flex-1 truncate font-medium">
                  {chunk.filename}
                </span>
                {chunk.page_number && (
                  <span className="text-xs text-slate-500 flex-shrink-0">
                    p. {chunk.page_number}
                  </span>
                )}
                <span className="text-xs text-slate-600">
                  {expanded === chunk.chunk_id ? "▲" : "▼"}
                </span>
              </div>
              {expanded === chunk.chunk_id && (
                <div className="px-3 pb-3 border-t border-slate-700/60">
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed whitespace-pre-wrap">
                    {chunk.content}
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
