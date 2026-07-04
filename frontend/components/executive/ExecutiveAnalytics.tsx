"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useExecutiveStore } from "@/store/executiveStore";
import type { AnalyticsSeries } from "@/services/executiveService";

// ── Chart config ──────────────────────────────────────────────────────────

const CHART_COLOR: Record<string, string> = {
  missions:          "#82c0a4",
  agent_events:      "#4a8c70",
  memory_ops:        "#4a8c70",
  voice_sessions:    "#96cead",
  governance_events: "#f87171",
  tool_calls:        "#fbbf24",
};

const CHART_LABELS: Record<string, string> = {
  missions:          "Mission Throughput",
  agent_events:      "Agent Utilization",
  memory_ops:        "Memory Operations",
  voice_sessions:    "Voice Usage",
  governance_events: "Governance Events",
  tool_calls:        "Tool Calls",
};

// ── Custom tooltip ────────────────────────────────────────────────────────

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: {name: string; value: number; color: string}[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "rgba(15,23,42,0.95)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "var(--radius-md)", padding: "8px 12px", fontSize: "var(--font-size-xs)" }}>
      <p style={{ margin: "0 0 5px", color: "var(--text-secondary)", fontWeight: 600 }}>{label}</p>
      {payload.map((p) => (
        <div key={p.name} style={{ display: "flex", justifyContent: "space-between", gap: 12, color: p.color }}>
          <span style={{ textTransform: "capitalize" }}>{(p.name as string).replace(/_/g," ")}</span>
          <span className="label-mono">{p.value}</span>
        </div>
      ))}
    </div>
  );
}

function buildAreaPath(values: number[], width: number, height: number) {
  if (values.length === 0) return "";

  const maxValue = Math.max(1, ...values);
  const stepX = values.length === 1 ? width : width / (values.length - 1);
  const points = values.map((value, index) => {
    const x = index * stepX;
    const y = height - (value / maxValue) * (height - 8) - 4;
    return { x, y };
  });

  const line = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(" ");

  const fill = `${line} L ${width} ${height} L 0 ${height} Z`;
  return fill;
}

function buildLinePath(values: number[], width: number, height: number) {
  if (values.length === 0) return "";

  const maxValue = Math.max(1, ...values);
  const stepX = values.length === 1 ? width : width / (values.length - 1);

  return values
    .map((value, index) => {
      const x = index * stepX;
      const y = height - (value / maxValue) * (height - 8) - 4;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

// ── Mini chart ────────────────────────────────────────────────────────────

function MiniChart({
  data, dataKey, color, label, total,
}: {
  data: AnalyticsSeries[]; dataKey: keyof AnalyticsSeries; color: string; label: string; total: number;
}) {
  const [type, setType] = useState<"area" | "bar">("area");
  const width = 220;
  const height = 64;
  const values = data.map((item) => {
    const value = item[dataKey];
    return typeof value === "number" ? value : 0;
  });
  const maxValue = Math.max(1, ...values);
  const areaPath = buildAreaPath(values, width, height);
  const linePath = buildLinePath(values, width, height);
  const barWidth = values.length === 0 ? width : Math.max(8, width / Math.max(values.length * 1.8, 1));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <div style={{ width: 4, height: 12, borderRadius: 2, background: color }} />
        <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--text-secondary)", flex: 1 }}>
          {label}
        </span>
        <span className="label-mono" style={{ fontSize: "var(--font-size-xs)", fontWeight: 700, color }}>
          {total.toLocaleString()}
        </span>
        <div style={{ display: "flex", gap: 2 }}>
          {(["area","bar"] as const).map((t) => (
            <button key={t} onClick={() => setType(t)} style={{ padding: "1px 6px", borderRadius: "var(--radius-sm)", border: `1px solid ${type===t ? color+"44" : "transparent"}`, background: type===t ? `${color}10` : "transparent", color: type===t ? color : "var(--text-muted)", fontSize: "9px", cursor: "pointer" }}>
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div style={{ height: 64, position: "relative" }}>
        <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{ width: "100%", height: "100%", display: "block" }}>
          {[0.25, 0.5, 0.75].map((ratio) => (
            <line
              key={ratio}
              x1="0"
              x2={width}
              y1={height * ratio}
              y2={height * ratio}
              stroke="rgba(255,255,255,0.05)"
              strokeDasharray="2 2"
            />
          ))}

          {type === "area" ? (
            <>
              <defs>
                <linearGradient id={`g-${String(dataKey)}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={color} stopOpacity={0.28} />
                  <stop offset="95%" stopColor={color} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <path d={areaPath} fill={`url(#g-${String(dataKey)})`} />
              <path d={linePath} fill="none" stroke={color} strokeWidth="1.75" strokeLinejoin="round" strokeLinecap="round" />
            </>
          ) : (
            values.map((value, index) => {
              const gap = values.length <= 1 ? 0 : (width - barWidth * values.length) / (values.length - 1);
              const x = index * (barWidth + Math.max(gap, 4));
              const barHeight = (value / maxValue) * (height - 8);
              const y = height - barHeight;

              return (
                <rect
                  key={`${String(dataKey)}-${index}`}
                  x={x}
                  y={y}
                  width={barWidth}
                  height={Math.max(barHeight, 2)}
                  rx="2"
                  fill={color}
                  opacity="0.9"
                />
              );
            })
          )}
        </svg>

        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4, fontSize: 8, color: "#737373" }}>
          {data.map((item) => (
            <span key={`${String(dataKey)}-${item.date}`}>{item.date}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────

export function ExecutiveAnalytics() {
  const analytics  = useExecutiveStore((s) => s.analytics);
  const isLoading  = useExecutiveStore((s) => s.isAnalyticsLoading);

  useEffect(() => {
    void useExecutiveStore.getState().loadAnalytics();
  }, []);

  const series = analytics?.series ?? [];
  const totals = analytics?.totals ?? {};

  const keys: (keyof AnalyticsSeries)[] = ["missions", "agent_events", "memory_ops", "voice_sessions", "governance_events", "tool_calls"];

  if (isLoading && series.length === 0) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 8, opacity: 0.4 }}>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} style={{ height: 85, borderRadius: "var(--radius-md)", background: "rgba(255,255,255,0.02)", border: "1px solid var(--border-subtle)" }} />
        ))}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
          7-day operational analytics
        </span>
        {isLoading && (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 0.9, ease: "linear" }}
            style={{ width: 10, height: 10, border: "2px solid var(--border-default)", borderTopColor: "var(--accent)", borderRadius: "50%", marginLeft: "auto" }}
          />
        )}
      </div>

      {/* Charts grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        {keys.map((key) => (
          <motion.div
            key={key}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            style={{
              padding:      "10px 12px",
              borderRadius: "var(--radius-md)",
              border:       `1px solid ${CHART_COLOR[key]}18`,
              background:   `${CHART_COLOR[key]}04`,
            }}
          >
            <MiniChart
              data={series}
              dataKey={key}
              color={CHART_COLOR[key]}
              label={CHART_LABELS[key]}
              total={totals[key] ?? 0}
            />
          </motion.div>
        ))}
      </div>
    </div>
  );
}
