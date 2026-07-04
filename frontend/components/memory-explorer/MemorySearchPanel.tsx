"use client";

import { useState, useRef, KeyboardEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useMemoryExplorerStore } from "@/store/memoryExplorerStore";
import { MemoryRecord, MemoryType } from "@/services/memoryExplorerService";

// ── Constants ─────────────────────────────────────────────────────────────

const TYPE_OPTIONS: { value: string; label: string; color: string }[] = [
  { value: "all",        label: "All Types",  color: "var(--accent)"           },
  { value: "episodic",   label: "Episodic",   color: "var(--agent-planner)"    },
  { value: "semantic",   label: "Semantic",   color: "var(--agent-research)"   },
  { value: "reflection", label: "Reflection", color: "var(--agent-critic)"     },
  { value: "voice",      label: "Voice",      color: "var(--agent-optimizer)"  },
  { value: "browser",    label: "Browser",    color: "var(--agent-memory)"     },
  { value: "workspace",  label: "Workspace",  color: "var(--agent-orchestrator)" },
];

const TYPE_COLOR: Record<string, string> = Object.fromEntries(
  TYPE_OPTIONS.map((t) => [t.value, t.color])
);

function typeBadge(mt: MemoryType | string) {
  return TYPE_COLOR[mt] ?? "var(--text-muted)";
}

function scoreBar(score: number | null) {
  if (score === null) return null;
  const pct = Math.round(score * 100);
  const color = score > 0.8 ? "var(--color-success)" : score > 0.5 ? "var(--accent)" : "var(--color-warning)";
  return { pct, color };
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1)  return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

// ── Result card ──────────────────────────────────────────────────────────

function MemoryResultCard({
  record,
  isSelected,
  onSelect,
}: {
  record: MemoryRecord;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const color = typeBadge(record.memory_type);
  const bar   = scoreBar(record.similarity_score);

  return (
    <motion.button
      onClick={onSelect}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        display:        "flex",
        flexDirection:  "column",
        gap:            8,
        padding:        "12px 14px",
        borderRadius:   "var(--radius-lg)",
        border:         `1px solid ${isSelected ? color + "55" : "var(--border-default)"}`,
        background:     isSelected ? `${color}08` : "#ffffff",
        cursor:         "pointer",
        textAlign:      "left",
        width:          "100%",
        boxShadow:      isSelected ? `0 0 0 1px ${color}33, var(--shadow-sm)` : "var(--shadow-xs)",
        transition:     "border-color 0.12s, box-shadow 0.12s, background 0.12s",
      }}
    >
      {/* Row 1: type badge + agent + time */}
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span
          style={{
            fontSize:   "var(--font-size-xs)",
            fontWeight: 600,
            padding:    "1px 7px",
            borderRadius: "var(--radius-pill)",
            background: `${color}14`,
            color,
            whiteSpace: "nowrap",
          }}
        >
          {record.memory_type}
        </span>
        {record.concept && (
          <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--text-secondary)" }}>
            {record.concept}
          </span>
        )}
        {record.agent && (
          <span style={{ fontSize: "var(--font-size-xs)", color, fontWeight: 500 }}>
            {record.agent}
          </span>
        )}
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", marginLeft: "auto", whiteSpace: "nowrap" }}>
          {relativeTime(record.created_at)}
        </span>
      </div>

      {/* Row 2: content preview */}
      <p
        style={{
          margin:        0,
          fontSize:      "var(--font-size-sm)",
          color:         "var(--text-secondary)",
          lineHeight:    1.5,
          display:       "-webkit-box",
          WebkitLineClamp: 2,
          WebkitBoxOrient: "vertical" as const,
          overflow:      "hidden",
        }}
      >
        {record.content}
      </p>

      {/* Row 3: score + meta */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {bar && (
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <div
              style={{
                width:        60,
                height:       3,
                borderRadius: 999,
                background:   "var(--border-subtle)",
                overflow:     "hidden",
              }}
            >
              <div style={{ width: `${bar.pct}%`, height: "100%", background: bar.color, borderRadius: 999 }} />
            </div>
            <span style={{ fontSize: "var(--font-size-xs)", color: bar.color, fontWeight: 600 }}>
              {bar.pct}%
            </span>
          </div>
        )}
        {record.retrieval_count > 0 && (
          <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
            {record.retrieval_count}× retrieved
          </span>
        )}
        {record.mission_id && (
          <span
            className="label-mono"
            style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 120 }}
          >
            {record.mission_id.slice(0, 8)}…
          </span>
        )}
      </div>
    </motion.button>
  );
}

// ── Main component ────────────────────────────────────────────────────────

export function MemorySearchPanel() {
  const query          = useMemoryExplorerStore((s) => s.searchQuery);
  const results        = useMemoryExplorerStore((s) => s.searchResults);
  const isSearching    = useMemoryExplorerStore((s) => s.isSearching);
  const searchError    = useMemoryExplorerStore((s) => s.searchError);
  const typeFilter     = useMemoryExplorerStore((s) => s.memoryTypeFilter);
  const minScore       = useMemoryExplorerStore((s) => s.minScore);
  const selectedRecord = useMemoryExplorerStore((s) => s.selectedRecord);
  const setQuery       = useMemoryExplorerStore((s) => s.setSearchQuery);
  const setTypeFilter  = useMemoryExplorerStore((s) => s.setMemoryTypeFilter);
  const setMinScore    = useMemoryExplorerStore((s) => s.setMinScore);
  const setSelected    = useMemoryExplorerStore((s) => s.setSelectedRecord);
  const search         = useMemoryExplorerStore((s) => s.search);

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") search();
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, height: "100%" }}>
      {/* Search input */}
      <div style={{ display: "flex", gap: 8 }}>
        <div style={{ flex: 1, position: "relative" }}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search memories — semantic, episodic, reflection…"
            className="premium-input"
            style={{ width: "100%", paddingLeft: 36, fontSize: "var(--font-size-sm)" }}
          />
          <span
            style={{
              position:   "absolute",
              left:       12,
              top:        "50%",
              transform:  "translateY(-50%)",
              color:      "var(--text-placeholder)",
              fontSize:   14,
              pointerEvents: "none",
            }}
          >
            ⌕
          </span>
        </div>
        <motion.button
          onClick={search}
          disabled={isSearching || !query.trim()}
          whileHover={!isSearching && query.trim() ? { scale: 1.02 } : {}}
          whileTap={!isSearching && query.trim() ? { scale: 0.97 } : {}}
          className="btn-primary"
          style={{
            padding:    "0 18px",
            fontSize:   "var(--font-size-sm)",
            opacity:    isSearching || !query.trim() ? 0.5 : 1,
            cursor:     isSearching || !query.trim() ? "not-allowed" : "pointer",
            whiteSpace: "nowrap",
          }}
        >
          {isSearching ? "Searching…" : "Search"}
        </motion.button>
      </div>

      {/* Filters row */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        {/* Memory type chips */}
        <div style={{ display: "flex", gap: 4 }}>
          {TYPE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setTypeFilter(opt.value)}
              style={{
                padding:      "3px 9px",
                borderRadius: "var(--radius-pill)",
                border:       `1px solid ${typeFilter === opt.value ? opt.color : "var(--border-default)"}`,
                background:   typeFilter === opt.value ? `${opt.color}12` : "transparent",
                color:        typeFilter === opt.value ? opt.color : "var(--text-muted)",
                fontSize:     "var(--font-size-xs)",
                fontWeight:   typeFilter === opt.value ? 600 : 500,
                cursor:       "pointer",
                whiteSpace:   "nowrap",
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* Min score slider */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginLeft: "auto" }}>
          <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", whiteSpace: "nowrap" }}>
            Min score
          </span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={minScore}
            onChange={(e) => setMinScore(parseFloat(e.target.value))}
            style={{ width: 80, accentColor: "var(--accent)" }}
          />
          <span className="label-mono" style={{ fontSize: "var(--font-size-xs)", color: "var(--accent)", minWidth: 28 }}>
            {Math.round(minScore * 100)}%
          </span>
        </div>
      </div>

      {/* Error */}
      <AnimatePresence>
        {searchError && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            style={{
              padding:      "8px 12px",
              borderRadius: "var(--radius-md)",
              background:   "rgba(220,38,38,0.06)",
              border:       "1px solid rgba(220,38,38,0.2)",
              color:        "var(--color-error)",
              fontSize:     "var(--font-size-sm)",
            }}
          >
            {searchError}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Results count */}
      {results.length > 0 && !isSearching && (
        <p style={{ margin: 0, fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
          {results.length} result{results.length !== 1 ? "s" : ""} across all memory stores
        </p>
      )}

      {/* Empty state */}
      {!isSearching && results.length === 0 && query.trim() && !searchError && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "40px 0", color: "var(--text-muted)", gap: 8 }}>
          <span style={{ fontSize: 28 }}>⌀</span>
          <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--text-secondary)", fontWeight: 500 }}>No memories found</p>
          <p style={{ margin: 0, fontSize: "var(--font-size-xs)" }}>Try a broader query or different memory type filter</p>
        </div>
      )}

      {!query.trim() && results.length === 0 && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "48px 0", color: "var(--text-muted)", gap: 10 }}>
          <div style={{ fontSize: 32, opacity: 0.3 }}>◎</div>
          <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--text-secondary)", fontWeight: 500 }}>
            Search across all memory stores
          </p>
          <p style={{ margin: 0, fontSize: "var(--font-size-xs)", textAlign: "center", maxWidth: 260, lineHeight: 1.5 }}>
            Queries episodic, semantic, and reflection memory simultaneously using vector similarity
          </p>
        </div>
      )}

      {/* Result list */}
      {results.length > 0 && (
        <div
          style={{ display: "flex", flexDirection: "column", gap: 8, overflowY: "auto", flex: 1 }}
          className="cortex-scroll"
        >
          {results.map((rec) => (
            <MemoryResultCard
              key={rec.id}
              record={rec}
              isSelected={selectedRecord?.id === rec.id}
              onSelect={() => setSelected(selectedRecord?.id === rec.id ? null : rec)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
