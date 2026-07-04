"use client"

import type { Citation } from "@/types/workspace"

interface Props {
  citations: Citation[]
}

export function CitationViewer({ citations }: Props) {
  if (!citations.length) return null

  return (
    <div className="flex flex-col gap-2 mt-4">
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
        Sources
      </p>
      {citations.map((c, i) => (
        <div
          key={`${c.citation_id}-${i}`}
          className="border border-slate-700 rounded-lg p-3 bg-slate-800/40"
        >
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-bold text-[#82c0a4] bg-[#82c0a4]/10 px-2 py-0.5 rounded">
              {c.citation_id}
            </span>
            <span className="text-xs text-slate-300 font-medium truncate">{c.filename}</span>
            {c.page_number && (
              <span className="ml-auto text-xs text-slate-500">p. {c.page_number}</span>
            )}
          </div>
          <p className="text-xs text-slate-400 leading-relaxed line-clamp-3">{c.excerpt}</p>
          <div className="flex items-center gap-2 mt-1">
            <div
              className="h-1 rounded-full bg-[#82c0a4]/30"
              style={{ width: `${Math.round(c.score * 100)}%`, maxWidth: "100%" }}
            />
            <span className="text-xs text-slate-600">
              {Math.round(c.score * 100)}% relevance
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}
