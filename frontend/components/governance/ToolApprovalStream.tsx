"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useGovernanceCenterStore } from "@/store/governanceCenterStore";
import type { GovernanceEvent, EventDecision } from "@/services/governanceCenterService";

// ── Constants ─────────────────────────────────────────────────────────────

const DECISION_CONFIG: Record<EventDecision, { color: string; bg: string; label: string; icon: string }> = {
  approved: { color: "#34d399", bg: "rgba(52,211,153,0.10)", label: "Approved", icon: "✓" },
  blocked:  { color: "#f87171", bg: "rgba(248,113,113,0.10)", label: "Blocked",  icon: "✕" },
  warned:   { color: "#fbbf24", bg: "rgba(251,191,36,0.10)",  label: "Warning",  icon: "⚠" },
};

const EVENT_TYPE_LABELS: Record<string, string> = {
  tool_approved:    "Tool Allowed",
  tool_blocked:     "Tool Blocked",
  memory_approved:  "Memory Access",
  mission_approved: "Mission Approved",
  guardrail_blocked:"Guardrail Block",
  policy_decision:  "Policy Decision",
};

const RISK_LEVEL_COLORS: Record<string, string> = {
  low:      "#34d399",
  medium:   "#fbbf24",
  high:     "#f87171",
  critical: "#dc2626",
};

function relTime(iso: string): string {
  const d = Date.now() - new Date(iso).getTime();
  if (d < 5000)    return "just now";
  if (d < 60000)   return `${Math.floor(d / 1000)}s`;
  if (d < 3600000) return `${Math.floor(d / 60000)}m`;
  return `${Math.floor(d / 3600000)}h`;
}

// ── Filter chip ───────────────────────────────────────────────────────────

function FilterChip({
  label, active, color, onClick,
}: { label: string; active: boolean; color: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding:      "3px 10px",
        borderRadius: "var(--radius-pill)",
        border:       `1px solid ${active ? color + "66" : "var(--border-default)"}`,
        background:   active ? `${color}12` : "transparent",
        color:        active ? color : "var(--text-muted)",
        fontSize:     "var(--font-size-xs)",
        fontWeight:   active ? 600 : 500,
        cursor:       "pointer",
        transition:   "all 0.12s",
      }}
    >
      {label}
    </button>
  );
}

// ── Event row ─────────────────────────────────────────────────────────────

function EventRow({ event, index }: { event: GovernanceEvent; index: number }) {
  const cfg = DECISION_CONFIG[event.decision] ?? DECISION_CONFIG.approved;
  const rl  = RISK_LEVEL_COLORS[event.risk_level] ?? "#a3a3a3";

  return (
    <motion.div
      key={event.id}
      layout
      initial={{ opacity: 0, x: -12, height: 0 }}
      animate={{ opacity: 1, x: 0, height: "auto" }}
      exit={{ opacity: 0, x: 12, height: 0 }}
      transition={{ duration: 0.2, delay: Math.min(index * 0.03, 0.15) }}
      style={{
        display:      "flex",
        alignItems:   "flex-start",
        gap:          10,
        padding:      "9px 10px",
        borderRadius: "var(--radius-md)",
        border:       `1px solid ${event.decision === "blocked" ? "rgba(248,113,113,0.15)" : "var(--border-subtle)"}`,
        background:   event.decision === "blocked" ? "rgba(248,113,113,0.04)" : "rgba(255,255,255,0.01)",
        transition:   "background 0.2s",
      }}
    >
      {/* Decision icon */}
      <div
        style={{
          width:        26,
          height:       26,
          borderRadius: "var(--radius-sm)",
          background:   cfg.bg,
          border:       `1px solid ${cfg.color}33`,
          display:      "flex",
          alignItems:   "center",
          justifyContent: "center",
          color:        cfg.color,
          fontSize:     11,
          fontWeight:   700,
          flexShrink:   0,
          marginTop:    1,
        }}
      >
        {cfg.icon}
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
          <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--text-primary)" }}>
            {EVENT_TYPE_LABELS[event.event_type] ?? event.event_type}
          </span>
          {/* Risk level */}
          <span style={{
            fontSize:     "10px",
            fontWeight:   600,
            color:        rl,
            background:   `${rl}15`,
            padding:      "0 6px",
            borderRadius: "var(--radius-pill)",
          }}>
            {event.risk_level.toUpperCase()}
          </span>
        </div>
        <p style={{ margin: 0, fontSize: "var(--font-size-xs)", color: "var(--text-secondary)", lineHeight: 1.4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          <span style={{ color: "var(--text-muted)" }}>{event.agent}</span>
          {" · "}
          {event.action.slice(0, 80)}{event.action.length > 80 ? "…" : ""}
        </p>
        {event.reason && (
          <p style={{ margin: "2px 0 0", fontSize: "10px", color: "var(--text-muted)", lineHeight: 1.3 }}>
            {event.reason.slice(0, 100)}
          </p>
        )}
      </div>

      {/* Right: time + decision pill */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4, flexShrink: 0 }}>
        <span className="label-mono" style={{ fontSize: "10px", color: "var(--text-muted)" }}>
          {relTime(event.timestamp)}
        </span>
        <span style={{
          fontSize:     "10px",
          fontWeight:   600,
          color:        cfg.color,
          background:   cfg.bg,
          padding:      "1px 7px",
          borderRadius: "var(--radius-pill)",
          border:       `1px solid ${cfg.color}33`,
        }}>
          {cfg.label}
        </span>
      </div>
    </motion.div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────

export function ToolApprovalStream() {
  const events         = useGovernanceCenterStore((s) => s.events);
  const isLoading      = useGovernanceCenterStore((s) => s.isEventsLoading);
  const decisionFilter = useGovernanceCenterStore((s) => s.decisionFilter);
  const setDecision    = useGovernanceCenterStore((s) => s.setDecisionFilter);
  const loadEvents     = useGovernanceCenterStore((s) => s.loadEvents);
  const intervalRef    = useRef<ReturnType<typeof setInterval> | null>(null);

  // Auto-refresh every 5s
  useEffect(() => {
    loadEvents();
    intervalRef.current = setInterval(loadEvents, 5000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [loadEvents, decisionFilter]);

  const allEvents = events?.events ?? [];

  // Client-side filter to tool events only
  const toolTypes = new Set(["tool_approved", "tool_blocked", "memory_approved", "mission_approved"]);
  const filtered  = allEvents.filter((e) => toolTypes.has(e.event_type));

  // Count by decision
  const approved = filtered.filter((e) => e.decision === "approved").length;
  const blocked  = filtered.filter((e) => e.decision === "blocked").length;
  const warned   = filtered.filter((e) => e.decision === "warned").length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
        <MiniStat label="Approved" value={approved} color="#34d399" />
        <MiniStat label="Blocked"  value={blocked}  color="#f87171" />
        <MiniStat label="Warned"   value={warned}   color="#fbbf24" />
      </div>

      {/* Decision filter chips */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        <FilterChip label="All"      active={!decisionFilter}           color="var(--accent)" onClick={() => setDecision(null)}       />
        <FilterChip label="Approved" active={decisionFilter === "approved"} color="#34d399" onClick={() => setDecision("approved")}  />
        <FilterChip label="Blocked"  active={decisionFilter === "blocked"}  color="#f87171" onClick={() => setDecision("blocked")}   />
        <FilterChip label="Warned"   active={decisionFilter === "warned"}   color="#fbbf24" onClick={() => setDecision("warned")}    />
      </div>

      {/* Stream */}
      {isLoading && filtered.length === 0 ? (
        <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-muted)", fontSize: "var(--font-size-sm)", padding: "12px 0" }}>
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 0.9, ease: "linear" }}
            style={{ width: 12, height: 12, border: "2px solid var(--border-default)", borderTopColor: "#34d399", borderRadius: "50%" }}
          />
          Connecting to approval stream…
        </div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: "center", padding: "24px 0", color: "var(--text-muted)" }}>
          <div style={{ fontSize: 22, opacity: 0.3, marginBottom: 6 }}>◈</div>
          <p style={{ margin: 0, fontSize: "var(--font-size-sm)" }}>No events yet</p>
        </div>
      ) : (
        <div
          style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 380, overflowY: "auto" }}
          className="cortex-scroll"
        >
          <AnimatePresence initial={false}>
            {filtered.map((ev, i) => (
              <EventRow key={ev.id} event={ev} index={i} />
            ))}
          </AnimatePresence>
        </div>
      )}

      <p style={{ margin: 0, fontSize: "var(--font-size-xs)", color: "var(--text-muted)", textAlign: "center" }}>
        Live · refreshes every 5s {isLoading && <span style={{ opacity: 0.6 }}>↻</span>}
      </p>
    </div>
  );
}

function MiniStat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{
      display:       "flex",
      flexDirection: "column",
      gap:           1,
      padding:       "7px 10px",
      borderRadius:  "var(--radius-md)",
      border:        `1px solid ${color}20`,
      background:    `${color}06`,
    }}>
      <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>{label}</span>
      <span className="label-mono" style={{ fontSize: "var(--font-size-lg)", fontWeight: 700, color }}>{value}</span>
    </div>
  );
}
