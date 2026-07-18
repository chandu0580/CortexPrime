"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { useKnowledgeSearch } from "@/hooks/queries/useKnowledge"
import { Search, BookOpen, FileText, Library } from "lucide-react"
import { Button, Input, EmptyState, Spinner } from "@/components/enterprise/ui"

export default function KnowledgeExplorer() {
  const [query, setQuery] = useState("")
  const [search, setSearch] = useState("")
  const { data, isLoading } = useKnowledgeSearch(search)
  const entries = data?.entries ?? []

  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="type-heading-xl text-[var(--text-primary)]">Knowledge Explorer</h1>
        <p className="type-body text-[var(--text-muted)] mt-1">Search indexed knowledge and mission history</p>
      </div>

      <div className="surface-panel p-5">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
            <input
              className="premium-input pl-10"
              placeholder="Search knowledge base..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && setSearch(query)}
            />
          </div>
          <Button onClick={() => setSearch(query)}>Search</Button>
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Spinner />
        </div>
      )}

      {search && !isLoading && (
        <div className="surface-panel p-5">
          <div className="flex items-center gap-2 mb-4">
            <BookOpen className="w-4 h-4 text-[var(--accent)]" />
            <h2 className="type-heading-sm text-[var(--text-primary)]">
              Results ({data?.total ?? 0})
            </h2>
          </div>
          {entries.length === 0 ? (
            <EmptyState
              icon={<Library className="w-12 h-12" />}
              title="No results found"
              description="Try different keywords or broaden your search"
            />
          ) : (
            <div className="space-y-3">
              {entries.map((entry, i) => (
                <motion.div
                  key={entry.id || i}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.03 }}
                  className="p-4 rounded-xl bg-[var(--surface-raised)]"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <FileText className="w-3.5 h-3.5 text-[var(--accent)]" />
                    <h3 className="type-body-sm text-[var(--text-primary)] font-semibold">{entry.title}</h3>
                  </div>
                  <p className="type-body-sm text-[var(--text-secondary)] line-clamp-2">{entry.content}</p>
                  <div className="flex items-center gap-3 mt-2">
                    <span className="type-caption text-[var(--text-muted)]">{entry.source}</span>
                    <span className="type-caption text-[var(--text-muted)]">
                      Confidence: {(entry.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
