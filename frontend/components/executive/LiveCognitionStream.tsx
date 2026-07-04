"use client";

import { useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useCognitionStore } from "@/store/cognitionStore";
import type { CognitionEvent } from "@/types/cognition";

// ── Agent identity ────────────────────────────────────────────────────────

const AGENT_COLORS: Record<string, string> = {
  orchestrator: "#82c0a4",
  planner:      "#4a8c70",
  research:     "#4a8c70",
  critic:       "#f9a825",
  optimizer:    "#96cead",
  memory:       "#737373",
  system:       "#737373",
};

const EVENT_ICONS: Record<string, string> = {
  mission_started:    "◎",
  mission_completed:  "✓",
  agent_started:      "⊙",
  agent_completed:    "⊛",
  tool_called:        "⊗",
  tool_completed:     "⊕",
  memory_retrieved:   "◈",
  memory_stored:      "◉",
  response_generated: "→",
  thinking:           "⟳",
  planning:           "⊞",
  research:           "⊝",
  default:            "·",
};

function agentColor(agent: string): string {
  return AGENT_COLORS[agent?.toLowerCase()] ?? "#a3a3a3";
}

function eventIcon(type: string): string {
  return EVENT_ICONS[type] ?? EVENT_ICONS.default;
}

function relTime(ts: number | string | undefined): string {
  if (!ts) return "";
  const ms = typeof ts === "number" ? ts : new Date(ts).getTime();
  const d  = Date.now() - ms;
  if (d < 5000)    return "now";
  if (d < 60000)   return `${Math.floor(d/1000)}s`;
  if (d < 3600000) return `${Math.floor(d/60000)}m`;
  return "";
}

// ── Event row ─────────────────────────────────────────────────────────────

function EventRow({ ev, isFirst }: { ev: CognitionEvent; isFirst: boolean }) {
  const color = agentColor(ev.agent);
  const icon  = eventIcon(ev.event_type);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -12, height: 0 }}
      animate={{ opacity: 1, x: 0, height: "auto" }}
      exit={{ opacity: 0, height: 0, marginBottom: 0 }}
      transition={{ duration: 0.22 }}
      style={{
        display:      "flex",
        alignItems:   "flex-start",
        gap:          8,
        padding:      "6px 8px",
        borderRadius: "var(--radius-md)",
        background:   isFirst ? `${color}08` : "transparent",
        border:       isFirst ? `1px solid ${color}25` : "1px solid transparent",
        transition:   "background 0.3s",
      }}
    >
      {/* Icon + dot */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2, flexShrink: 0, paddingTop: 2 }}>
        <span style={{ fontSize: 11, color, lineHeight: 1 }}>{icon}</span>
        {isFirst && (
          <motion.div
            animate={{ opacity: [1, 0.2, 1] }}
            transition={{ repeat: Infinity, duration: 1.2 }}
            style={{ width: 3, height: 3, borderRadius: "50%", background: color }}
          />
        )}
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 1 }}>
          <span style={{
            fontSize:   "10px",
            fontWeight: 700,
            color,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}>
            {ev.agent}
          </span>
          <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>
            {ev.event_type?.replace(/_/g," ")}
          </span>
        </div>
        <p style={{
          margin:     0,
          fontSize:   "var(--font-size-xs)",
          color:      isFirst ? "var(--text-primary)" : "var(--text-secondary)",
          lineHeight: 1.4,
          overflow:   "hidden",
          display:    "-webkit-box",
          WebkitLineClamp: 2,
          WebkitBoxOrient: "vertical" as const,
        }}>
          {ev.message}
        </p>
      </div>

      {/* Timestamp */}
      <span className="label-mono" style={{ fontSize: "10px", color: "var(--text-muted)", flexShrink: 0 }}>
        {relTime(ev.timestamp)}
      </span>
    </motion.div>
  );
}

// ── Thinking indicator ────────────────────────────────────────────────────

function ThinkingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      style={{ display: "flex", alignItems: "center", gap: 6, padding: "5px 8px" }}
    >
      <div style={{ display: "flex", gap: 3 }}>
        {[0,1,2].map((i) => (
          <motion.div
            key={i}
            animate={{ y: [0, -4, 0] }}
            transition={{ repeat: Infinity, duration: 0.8, delay: i * 0.15 }}
            style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--accent)" }}
          />
        ))}
      </div>
      <span style={{ fontSize: "var(--font-size-xs)", color: "var(--accent)", fontStyle: "italic" }}>
        Reasoning…
      </span>
    </motion.div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────

export function LiveCognitionStream() {
  const events     = useCognitionStore((s) => s.events);
  const isStreaming = useCognitionStore((s) => s.isStreaming);
  const scrollRef   = useRef<HTMLDivElement>(null);

  // Auto-scroll to top when new events arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [events.length]);

  const recent = events.slice(0, 25);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0, height: "100%" }}>
      {/* Stream header */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8, flexShrink: 0 }}>
        <motion.div
          animate={{ opacity: [1, 0.4, 1] }}
          transition={{ repeat: Infinity, duration: 1.4 }}
          style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--accent)" }}
        />
        <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 700, color: "var(--accent)", letterSpacing: "0.06em" }}>
          LIVE
        </span>
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
          Cognition Stream
        </span>
        <span className="label-mono" style={{ marginLeft: "auto", fontSize: "10px", color: "var(--text-muted)" }}>
          {recent.length} events
        </span>
      </div>

      {/* Thinking indicator */}
      <AnimatePresence>
        {isStreaming && <ThinkingIndicator />}
      </AnimatePresence>

      {/* Event list */}
      {recent.length === 0 ? (
        <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 8, opacity: 0.4 }}>
          <div style={{ display: "flex", gap: 3 }}>
            {[0,1,2,3].map((i) => (
              <motion.div
                key={i}
                animate={{ opacity: [0.2, 0.8, 0.2] }}
                transition={{ repeat: Infinity, duration: 1.5, delay: i * 0.3 }}
                style={{ width: 3, height: 24, borderRadius: 2, background: "var(--accent)" }}
              />
            ))}
          </div>
          <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
            Waiting for cognition events…
          </span>
        </div>
      ) : (
        <div
          ref={scrollRef}
          style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 3 }}
          className="cortex-scroll"
        >
          <AnimatePresence initial={false}>
            {recent.map((ev, i) => (
              <EventRow
                key={ev.event_id ?? `${ev.agent}-${ev.timestamp}-${i}`}
                ev={ev}
                isFirst={i === 0}
              />
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
