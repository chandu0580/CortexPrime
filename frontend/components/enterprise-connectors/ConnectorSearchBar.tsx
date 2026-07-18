"use client";

import { motion } from "framer-motion";
import { Search, Filter, LayoutGrid, List } from "lucide-react";
import { dur } from "@/lib/motion-tokens";
import type { ConnectorStatus } from "./types";

export type FilterOption = "all" | ConnectorStatus;
export type ViewMode = "grid" | "list";

interface TabConfig {
  value: FilterOption;
  label: string;
  dotColor?: string;
}

const TABS: TabConfig[] = [
  { value: "all",                label: "All Integrations" },
  { value: "connected",          label: "Connected",          dotColor: "var(--success)" },
  { value: "disconnected",       label: "Not Connected",      dotColor: "var(--danger)" },
  { value: "healthy",            label: "Healthy",            dotColor: "var(--accent-primary)" },
  { value: "needs_configuration",label: "Issues",             dotColor: "var(--warning)" },
];

interface ConnectorSearchBarProps {
  query: string;
  onQueryChange: (q: string) => void;
  activeFilter: FilterOption;
  onFilterChange: (f: FilterOption) => void;
  counts?: Partial<Record<FilterOption, number>>;
  viewMode?: ViewMode;
  onViewModeChange?: (v: ViewMode) => void;
}

export default function ConnectorSearchBar({
  query,
  onQueryChange,
  activeFilter,
  onFilterChange,
  counts,
  viewMode = "grid",
  onViewModeChange,
}: ConnectorSearchBarProps) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "var(--space-3)",
        flexWrap: "wrap",
      }}
    >
      {/* ── Tab filters (left) ── */}
      <div
        style={{ display: "flex", gap: 2, flexWrap: "wrap" }}
        role="tablist"
        aria-label="Filter integrations by status"
      >
        {TABS.map((tab) => {
          const isActive = activeFilter === tab.value;
          const count = counts?.[tab.value];

          return (
            <motion.button
              key={tab.value}
              role="tab"
              aria-selected={isActive}
              whileTap={{ scale: 0.96 }}
              onClick={() => onFilterChange(tab.value)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                padding: "6px 12px",
                borderRadius: "var(--radius-pill)",
                border: `1px solid ${isActive ? "var(--accent-border)" : "var(--border)"}`,
                background: isActive ? "var(--accent-muted)" : "transparent",
                color: isActive ? "var(--accent-primary)" : "var(--text-secondary)",
                fontSize: "var(--font-size-xs)",
                fontWeight: 600,
                cursor: "pointer",
                transition: `all ${dur.snap}s ease`,
                letterSpacing: "-0.005em",
                whiteSpace: "nowrap",
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = "var(--surface-raised)";
                  e.currentTarget.style.color = "var(--text-primary)";
                  e.currentTarget.style.borderColor = "var(--border-strong)";
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.color = "var(--text-secondary)";
                  e.currentTarget.style.borderColor = "var(--border)";
                }
              }}
            >
              {tab.label}
              {count != null && (
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    minWidth: 18,
                    height: 18,
                    borderRadius: "var(--radius-pill)",
                    background: isActive ? "var(--accent-primary)" : "var(--surface-raised)",
                    color: isActive ? "var(--text-inverse)" : "var(--text-muted)",
                    fontSize: 10,
                    fontWeight: 700,
                    padding: "0 5px",
                    lineHeight: 1,
                  }}
                >
                  {count}
                </span>
              )}
            </motion.button>
          );
        })}
      </div>

      {/* ── Right: search + view toggle ── */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        {/* Search box */}
        <div style={{ position: "relative" }}>
          <Search
            size={13}
            style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-placeholder)", pointerEvents: "none" }}
          />
          <input
            type="search"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Search integrations..."
            aria-label="Search integrations"
            style={{
              height: 34,
              width: 200,
              paddingLeft: 30,
              paddingRight: 12,
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              color: "var(--text-primary)",
              fontSize: "var(--font-size-xs)",
              outline: "none",
              transition: `border-color ${dur.fast}s ease, box-shadow ${dur.fast}s ease`,
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "var(--accent-primary)";
              e.currentTarget.style.boxShadow = "0 0 0 2px var(--accent-muted)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "var(--border)";
              e.currentTarget.style.boxShadow = "none";
            }}
          />
        </div>

        {/* Filter icon */}
        <button
          aria-label="Advanced filters"
          style={{
            width: 34,
            height: 34,
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border)",
            background: "var(--surface)",
            color: "var(--text-muted)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            transition: `color ${dur.fast}s ease, border-color ${dur.fast}s ease`,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = "var(--text-primary)";
            e.currentTarget.style.borderColor = "var(--border-strong)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = "var(--text-muted)";
            e.currentTarget.style.borderColor = "var(--border)";
          }}
        >
          <Filter size={14} />
        </button>

        {/* View mode toggle */}
        <div
          style={{
            display: "flex",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            overflow: "hidden",
          }}
        >
          {(["grid", "list"] as ViewMode[]).map((mode) => {
            const isActive = viewMode === mode;
            return (
              <button
                key={mode}
                onClick={() => onViewModeChange?.(mode)}
                aria-label={mode === "grid" ? "Grid view" : "List view"}
                aria-pressed={isActive}
                style={{
                  width: 34,
                  height: 34,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  border: "none",
                  background: isActive ? "var(--accent-muted)" : "var(--surface)",
                  color: isActive ? "var(--accent-primary)" : "var(--text-muted)",
                  cursor: "pointer",
                  transition: `background ${dur.snap}s ease, color ${dur.snap}s ease`,
                }}
              >
                {mode === "grid" ? <LayoutGrid size={14} /> : <List size={14} />}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
