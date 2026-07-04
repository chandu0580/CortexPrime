"use client";

import { useEffect, useMemo, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from "recharts";
import { useGovernanceCenterStore } from "@/store/governanceCenterStore";

// ── Guardrail categories ──────────────────────────────────────────────────

const GUARDRAIL_COLORS: Record<string, string> = {
  prompt_injection:        "#f87171",
  jailbreak:               "#dc2626",
  role_override:           "#f97316",
  system_prompt_extraction:"#fb923c",
  harmful_intent:          "#ef4444",
  unsafe_tool_call:        "#fbbf24",
  browser_unsafe_action:   "#f59e0b",
  computer_unsafe_action:  "#f9a825",
  credential_leak:         "#a855f7",
  system_info_leak:        "#96cead",
  unsafe_output:           "#737373",
  policy_violation:        "#737373",
};

const GUARDRAIL_LABELS: Record<string, string> = {
  prompt_injection:        "Prompt Injection",
  jailbreak:               "Jailbreak Attempt",
  role_override:           "Role Override",
  system_prompt_extraction:"System Prompt Extract",
  harmful_intent:          "Harmful Intent",
  unsafe_tool_call:        "Unsafe Tool Call",
  browser_unsafe_action:   "Browser Unsafe",
  computer_unsafe_action:  "Computer Unsafe",
  credential_leak:         "Credential Harvest",
  system_info_leak:        "System Info Leak",
  unsafe_output:           "Unsafe Output",
  policy_violation:        "Policy Violation",
};

function getColor(key: string) {
  return GUARDRAIL_COLORS[key] ?? "#737373";
}

function getLabel(key: string) {
  return GUARDRAIL_LABELS[key] ?? key.replace(/_/g, " ");
}

// ── Threat row ────────────────────────────────────────────────────────────

function ThreatRow({ label, count, maxCount, color }: {
  label: string; count: number; maxCount: number; color: string;
}) {
  const pct = maxCount > 0 ? count / maxCount : 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      {/* Dot */}
      <div style={{ width: 6, height: 6, borderRadius: "50%", background: color, flexShrink: 0, boxShadow: `0 0 6px ${color}` }} />
      {/* Label */}
      <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-secondary)", minWidth: 160 }}>{label}</span>
      {/* Bar */}
      <div style={{ flex: 1, height: 4, borderRadius: 999, background: "rgba(255,255,255,0.04)", overflow: "hidden" }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct * 100}%` }}
          transition={{ duration: 0.7, ease: "easeOut" }}
          style={{
            height:     "100%",
            background: `linear-gradient(to right, ${color}99, ${color})`,
            borderRadius: 999,
            boxShadow:  `0 0 8px ${color}50`,
          }}
        />
      </div>
      {/* Count */}
      <span className="label-mono" style={{ fontSize: "var(--font-size-xs)", color, fontWeight: 700, minWidth: 28, textAlign: "right" }}>
        {count}
      </span>
    </div>
  );
}

// ── Recent violation card ─────────────────────────────────────────────────

interface ViolationRecord {
  violation_type: string;
  matched_rule:   string;
  layer:          string;
  text_preview:   string;
  timestamp:      number;
}

function ViolationCard({ v, index }: { v: ViolationRecord; index: number }) {
  const color = getColor(v.violation_type);
  const age   = Date.now() / 1000 - v.timestamp;
  const ageStr = age < 60 ? `${Math.round(age)}s ago` : age < 3600 ? `${Math.floor(age / 60)}m ago` : `${Math.floor(age / 3600)}h ago`;

  return (
    <motion.div
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      style={{
        display:       "flex",
        flexDirection: "column",
        gap:           4,
        padding:       "8px 10px",
        borderRadius:  "var(--radius-md)",
        border:        `1px solid ${color}22`,
        background:    `${color}06`,
        position:      "relative",
        overflow:      "hidden",
      }}
    >
      {/* Left accent */}
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 2, background: color, opacity: 0.7 }} />

      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ fontSize: "10px", fontWeight: 700, color, background: `${color}18`, padding: "0 6px", borderRadius: "var(--radius-pill)", border: `1px solid ${color}30` }}>
          {getLabel(v.violation_type)}
        </span>
        <span style={{ fontSize: "10px", color: "var(--text-muted)", marginLeft: "auto" }}>{v.layer}</span>
        <span className="label-mono" style={{ fontSize: "10px", color: "var(--text-muted)" }}>{ageStr}</span>
      </div>

      <p style={{ margin: 0, fontSize: "var(--font-size-xs)", color: "var(--text-secondary)", lineHeight: 1.4 }}>
        <span style={{ color: "var(--text-muted)" }}>Rule: </span>
        <strong>{v.matched_rule}</strong>
      </p>

      {v.text_preview && (
        <p style={{ margin: 0, fontSize: "10px", color: "var(--text-muted)", fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          "{v.text_preview}"
        </p>
      )}
    </motion.div>
  );
}

// ── Recharts tooltip ──────────────────────────────────────────────────────

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "rgba(15,23,42,0.95)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "var(--radius-md)", padding: "8px 12px", fontSize: "var(--font-size-xs)" }}>
      <p style={{ margin: "0 0 4px", color: "var(--text-secondary)", fontWeight: 600 }}>{getLabel(label ?? "")}</p>
      {payload.map((p) => (
        <div key={p.name} style={{ display: "flex", justifyContent: "space-between", gap: 14, color: p.color }}>
          <span>Count</span>
          <span className="label-mono">{p.value}</span>
        </div>
      ))}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────

export function GuardrailEvents() {
  const events    = useGovernanceCenterStore((s) => s.events);
  const isLoading = useGovernanceCenterStore((s) => s.isEventsLoading);
  const loadEvents = useGovernanceCenterStore((s) => s.loadEvents);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    loadEvents();
    intervalRef.current = setInterval(loadEvents, 8000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [loadEvents]);

  const summary = events?.guardrail_summary ?? {};

  // Sort summary by count desc
  const sortedSummary = useMemo(
    () => Object.entries(summary).sort(([, a], [, b]) => b - a),
    [summary]
  );

  const maxCount = sortedSummary.length > 0 ? sortedSummary[0][1] : 1;

  // Recent violations from the event stream
  const recentViolations: ViolationRecord[] = useMemo(() => {
    const guardrailEvents = (events?.events ?? []).filter((e) => e.event_type === "guardrail_blocked");
    return guardrailEvents.map((e) => ({
      violation_type: e.action,
      matched_rule:   e.action,
      layer:          "input",
      text_preview:   e.target,
      timestamp:      new Date(e.timestamp).getTime() / 1000,
    }));
  }, [events]);

  // Chart data
  const chartData = sortedSummary.slice(0, 8).map(([key, count]) => ({
    name:  key,
    count,
    fill:  getColor(key),
  }));

  const totalHits = sortedSummary.reduce((s, [, c]) => s + c, 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* Total hits badge */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{
          padding:      "6px 14px",
          borderRadius: "var(--radius-pill)",
          border:       totalHits > 0 ? "1px solid rgba(248,113,113,0.35)" : "1px solid var(--border-default)",
          background:   totalHits > 0 ? "rgba(248,113,113,0.08)" : "transparent",
        }}>
          <span className="label-mono" style={{ fontSize: "var(--font-size-xl)", fontWeight: 800, color: totalHits > 0 ? "#f87171" : "var(--text-muted)" }}>
            {totalHits}
          </span>
          <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", marginLeft: 6 }}>
            {totalHits === 1 ? "violation" : "violations"} detected
          </span>
        </div>
        {isLoading && (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 0.9, ease: "linear" }}
            style={{ width: 12, height: 12, border: "2px solid var(--border-default)", borderTopColor: "#f87171", borderRadius: "50%" }}
          />
        )}
      </div>

      {/* Threat distribution */}
      {sortedSummary.length > 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          {sortedSummary.map(([key, count]) => (
            <ThreatRow key={key} label={getLabel(key)} count={count} maxCount={maxCount} color={getColor(key)} />
          ))}
        </div>
      ) : (
        <div style={{ textAlign: "center", padding: "12px 0", color: "var(--text-muted)", fontSize: "var(--font-size-sm)" }}>
          No guardrail violations detected
        </div>
      )}

      {/* Trend bar chart */}
      {chartData.length > 0 && (
        <div>
          <p style={{ margin: "0 0 8px", fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Trend Overview
          </p>
          <div style={{ height: 140 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 2, right: 2, left: -24, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="name" tick={{ fontSize: 8, fill: "#737373" }} axisLine={false} tickLine={false}
                  tickFormatter={(v: string) => getLabel(v).split(" ")[0]} />
                <YAxis tick={{ fontSize: 8, fill: "#737373" }} axisLine={false} tickLine={false} />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                  {chartData.map((entry, i) => (
                    <rect key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Recent violations */}
      {recentViolations.length > 0 && (
        <div>
          <p style={{ margin: "0 0 8px", fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Recent Events
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 5, maxHeight: 200, overflowY: "auto" }} className="cortex-scroll">
            <AnimatePresence initial={false}>
              {recentViolations.slice(0, 15).map((v, i) => (
                <ViolationCard key={`${v.violation_type}-${v.timestamp}-${i}`} v={v} index={i} />
              ))}
            </AnimatePresence>
          </div>
        </div>
      )}
    </div>
  );
}
