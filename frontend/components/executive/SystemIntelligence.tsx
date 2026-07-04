"use client";

import { motion } from "framer-motion";
import { useExecutiveStore } from "@/store/executiveStore";
import type { SubsystemStatus, HealthItem } from "@/services/executiveService";

const EMPTY_SUBSYSTEMS: SubsystemStatus[] = [];
const EMPTY_HEALTH: HealthItem[] = [];

// ── Subsystem module ──────────────────────────────────────────────────────

const MODULE_ICONS: Record<string, string> = {
  "Voice Runtime":     "◉",
  "Memory Explorer":   "◎",
  "Governance Center": "⊕",
  "Replay Engine":     "▶",
  "Computer Agent":    "⊞",
  "Browser Agent":     "⊗",
};

const MODULE_HREFS: Record<string, string> = {
  "Voice Runtime":     "/voice",
  "Memory Explorer":   "/memory-explorer",
  "Governance Center": "/governance-center",
  "Replay Engine":     "/replay",
  "Computer Agent":    "/operator",
  "Browser Agent":     "/operator",
};

function statusColor(s: string) {
  return s === "online" ? "#34d399" : s === "degraded" ? "#fbbf24" : "#f87171";
}

function SubsystemModule({ sub, index }: { sub: SubsystemStatus; index: number }) {
  const color = statusColor(sub.status);
  const href  = MODULE_HREFS[sub.name] ?? "/";
  const icon  = MODULE_ICONS[sub.name] ?? "◈";

  return (
    <motion.a
      href={href}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06 }}
      whileHover={{ scale: 1.02 }}
      style={{
        display:        "flex",
        alignItems:     "center",
        gap:            10,
        padding:        "9px 11px",
        borderRadius:   "var(--radius-md)",
        border:         `1px solid ${color}20`,
        background:     `${color}06`,
        textDecoration: "none",
        position:       "relative",
        overflow:       "hidden",
        transition:     "border-color 0.12s",
        cursor:         "pointer",
      }}
    >
      {/* Left accent */}
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 2, background: color, opacity: 0.6, borderRadius: "2px 0 0 2px" }} />

      {/* Icon */}
      <span style={{ fontSize: 14, color, flexShrink: 0 }}>{icon}</span>

      {/* Text */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ margin: 0, fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--text-primary)" }}>
          {sub.name}
        </p>
        <p style={{ margin: 0, fontSize: "10px", color: "var(--text-muted)" }}>
          {sub.detail}
        </p>
      </div>

      {/* Value + status */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
        <span className="label-mono" style={{ fontSize: "var(--font-size-xs)", fontWeight: 700, color }}>
          {sub.value}
        </span>
        <span style={{
          fontSize:     "9px",
          fontWeight:   700,
          letterSpacing: "0.04em",
          color,
          background:   `${color}15`,
          padding:      "1px 5px",
          borderRadius: "var(--radius-pill)",
        }}>
          {sub.status.toUpperCase()}
        </span>
      </div>
    </motion.a>
  );
}

// ── Health item ───────────────────────────────────────────────────────────

function HealthCard({ item, index }: { item: HealthItem; index: number }) {
  const color =
    item.status === "healthy"  ? "#34d399" :
    item.status === "degraded" ? "#fbbf24" : "#f87171";

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: index * 0.05 }}
      style={{
        display:        "flex",
        flexDirection:  "column",
        gap:            5,
        padding:        "9px 10px",
        borderRadius:   "var(--radius-md)",
        border:         `1px solid ${color}20`,
        background:     `${color}06`,
        position:       "relative",
        overflow:       "hidden",
      }}
    >
      {/* Score arc mini */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--text-primary)" }}>
          {item.label}
        </span>
        <span
          className="label-mono"
          style={{ fontSize: "var(--font-size-xs)", fontWeight: 800, color }}
        >
          {Math.round(item.score)}
        </span>
      </div>

      {/* Score bar */}
      <div style={{ height: 3, borderRadius: 999, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${item.score}%` }}
          transition={{ duration: 0.9, ease: "easeOut" }}
          style={{
            height:     "100%",
            background: `linear-gradient(to right, ${color}80, ${color})`,
            borderRadius: 999,
            boxShadow:  `0 0 6px ${color}50`,
          }}
        />
      </div>

      {/* Detail */}
      <p style={{ margin: 0, fontSize: "10px", color: "var(--text-muted)" }}>
        {item.detail}
      </p>

      {/* Status dot */}
      <div style={{ position: "absolute", top: 8, right: 8 }}>
        <div style={{ width: 5, height: 5, borderRadius: "50%", background: color }} />
      </div>
    </motion.div>
  );
}

// ── System intelligence panel ─────────────────────────────────────────────

export function SystemIntelligence() {
  const subsystems = useExecutiveStore((s) => s.snapshot?.subsystems) ?? EMPTY_SUBSYSTEMS;
  const isLoading  = useExecutiveStore((s) => s.isLoading);

  if (isLoading && subsystems.length === 0) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} style={{ height: 52, borderRadius: "var(--radius-md)", background: "rgba(255,255,255,0.02)", border: "1px solid var(--border-subtle)" }} />
        ))}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {subsystems.map((sub, i) => (
        <SubsystemModule key={sub.name} sub={sub} index={i} />
      ))}
    </div>
  );
}

// ── AI health matrix ──────────────────────────────────────────────────────

export function AIHealthMatrix() {
  const health    = useExecutiveStore((s) => s.snapshot?.health_matrix) ?? EMPTY_HEALTH;
  const isLoading = useExecutiveStore((s) => s.isLoading);

  if (isLoading && health.length === 0) {
    return (
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} style={{ height: 72, borderRadius: "var(--radius-md)", background: "rgba(255,255,255,0.02)", border: "1px solid var(--border-subtle)" }} />
        ))}
      </div>
    );
  }

  const overall = health.length > 0
    ? Math.round(health.reduce((s, h) => s + h.score, 0) / health.length)
    : 0;
  const overallColor = overall >= 85 ? "#34d399" : overall >= 65 ? "#fbbf24" : "#f87171";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {/* Overall */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
          System Health
        </span>
        <div style={{ flex: 1, height: 4, borderRadius: 999, background: "var(--border-subtle)", overflow: "hidden" }}>
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${overall}%` }}
            transition={{ duration: 1, ease: "easeOut" }}
            style={{ height: "100%", background: `linear-gradient(to right, ${overallColor}60, ${overallColor})`, borderRadius: 999, boxShadow: `0 0 8px ${overallColor}50` }}
          />
        </div>
        <span className="label-mono" style={{ fontSize: "var(--font-size-xs)", fontWeight: 700, color: overallColor, minWidth: 28 }}>
          {overall}
        </span>
      </div>

      {/* Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
        {health.map((item, i) => (
          <HealthCard key={item.label} item={item} index={i} />
        ))}
      </div>
    </div>
  );
}
