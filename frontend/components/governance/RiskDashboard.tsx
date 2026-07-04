"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";
import { useGovernanceCenterStore } from "@/store/governanceCenterStore";
import type { RiskBucket, RiskSeries } from "@/services/governanceCenterService";

// ── Constants ─────────────────────────────────────────────────────────────

const RISK_COLORS = {
  low:      "#34d399",
  medium:   "#fbbf24",
  high:     "#f87171",
  critical: "#dc2626",
};

type Window = "today" | "7d" | "30d";
const WINDOWS: { id: Window; label: string }[] = [
  { id: "today", label: "Today"  },
  { id: "7d",    label: "7 Days" },
  { id: "30d",   label: "30 Days"},
];

// ── Custom tooltip ────────────────────────────────────────────────────────

function RiskTooltip({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  const total = payload.reduce((s, p) => s + (p.value || 0), 0);
  return (
    <div style={{
      background:   "rgba(15,23,42,0.95)",
      border:       "1px solid rgba(255,255,255,0.08)",
      borderRadius: "var(--radius-md)",
      padding:      "10px 14px",
      fontSize:     "var(--font-size-xs)",
    }}>
      <p style={{ margin: "0 0 6px", color: "var(--text-secondary)", fontWeight: 600 }}>{label}</p>
      {payload.map((p) => (
        <div key={p.name} style={{ display: "flex", justifyContent: "space-between", gap: 16, color: p.color }}>
          <span style={{ textTransform: "capitalize" }}>{p.name}</span>
          <span className="label-mono">{p.value}</span>
        </div>
      ))}
      <div style={{ borderTop: "1px solid rgba(255,255,255,0.06)", marginTop: 4, paddingTop: 4, display: "flex", justifyContent: "space-between", color: "var(--text-muted)" }}>
        <span>Total</span>
        <span className="label-mono">{total}</span>
      </div>
    </div>
  );
}

// ── Risk gauge (radial arc) ───────────────────────────────────────────────

function RiskGauge({ bucket }: { bucket: RiskBucket }) {
  const total = bucket.total || 1;
  const safeRatio = bucket.low / total;
  const score = Math.round(safeRatio * 100);
  const color = score >= 80 ? "#34d399" : score >= 60 ? "#fbbf24" : "#f87171";

  const r  = 40;
  const cx = 55;
  const cy = 55;
  const circumference = Math.PI * r;  // half-circle
  const offset = circumference * (1 - safeRatio);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
      <svg width={110} height={70} style={{ overflow: "visible" }}>
        {/* Track */}
        <path
          d={`M ${cx - r},${cy} A ${r},${r} 0 0 1 ${cx + r},${cy}`}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={6}
          strokeLinecap="round"
        />
        {/* Fill */}
        <motion.path
          d={`M ${cx - r},${cy} A ${r},${r} 0 0 1 ${cx + r},${cy}`}
          fill="none"
          stroke={color}
          strokeWidth={6}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1, ease: "easeOut" }}
          style={{ filter: `drop-shadow(0 0 6px ${color})` }}
        />
        <text x={cx} y={cy + 2} textAnchor="middle" style={{ fontSize: 18, fontWeight: 800, fill: color }}>
          {score}%
        </text>
        <text x={cx} y={cy + 16} textAnchor="middle" style={{ fontSize: 9, fill: "#737373", fontFamily: "monospace" }}>
          SAFE RATIO
        </text>
      </svg>
    </div>
  );
}

// ── Bucket bar ────────────────────────────────────────────────────────────

function BucketBar({ bucket }: { bucket: RiskBucket }) {
  const total = bucket.total || 1;
  const bars = [
    { key: "low",      color: RISK_COLORS.low,      label: "Low",      value: bucket.low      },
    { key: "medium",   color: RISK_COLORS.medium,   label: "Medium",   value: bucket.medium   },
    { key: "high",     color: RISK_COLORS.high,     label: "High",     value: bucket.high     },
    { key: "critical", color: RISK_COLORS.critical, label: "Critical", value: bucket.critical },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {bars.map(({ key, color, label, value }) => (
        <div key={key} style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: "var(--font-size-xs)", color, fontWeight: 500, minWidth: 56 }}>{label}</span>
          <div style={{ flex: 1, height: 4, borderRadius: 999, background: "rgba(255,255,255,0.05)", overflow: "hidden" }}>
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${(value / total) * 100}%` }}
              transition={{ duration: 0.7, ease: "easeOut" }}
              style={{ height: "100%", background: color, borderRadius: 999 }}
            />
          </div>
          <span className="label-mono" style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", minWidth: 28, textAlign: "right" }}>
            {value}
          </span>
        </div>
      ))}
      <p style={{ margin: "4px 0 0", fontSize: "var(--font-size-xs)", color: "var(--text-muted)", textAlign: "right" }}>
        {bucket.total.toLocaleString()} total
      </p>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────

export function RiskDashboard() {
  const risk      = useGovernanceCenterStore((s) => s.risk);
  const isLoading = useGovernanceCenterStore((s) => s.isRiskLoading);
  const loadRisk  = useGovernanceCenterStore((s) => s.loadRisk);
  const [window,  setWindowState] = useState<Window>("30d");
  const [chart, setChart] = useState<"area" | "bar">("area");

  useEffect(() => { loadRisk(); }, [loadRisk]);

  const activeBucket: RiskBucket | null =
    window === "today"  ? risk?.today ?? null :
    window === "7d"     ? risk?.seven_day ?? null :
    risk?.thirty_day ?? null;

  const series: RiskSeries[] = risk?.series ?? [];

  if (isLoading && !risk) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-muted)", fontSize: "var(--font-size-sm)", padding: "20px 0" }}>
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 0.9, ease: "linear" }}
          style={{ width: 14, height: 14, border: "2px solid var(--border-default)", borderTopColor: "var(--accent)", borderRadius: "50%" }}
        />
        Loading risk data…
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* Window selector */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", gap: 4 }}>
          {WINDOWS.map((w) => (
            <motion.button
              key={w.id}
              onClick={() => setWindowState(w.id)}
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.96 }}
              style={{
                padding:      "4px 12px",
                borderRadius: "var(--radius-pill)",
                border:       `1px solid ${window === w.id ? "var(--accent)" : "var(--border-default)"}`,
                background:   window === w.id ? "rgba(130,192,164,0.12)" : "transparent",
                color:        window === w.id ? "var(--accent)" : "var(--text-muted)",
                fontSize:     "var(--font-size-xs)",
                fontWeight:   window === w.id ? 600 : 500,
                cursor:       "pointer",
              }}
            >
              {w.label}
            </motion.button>
          ))}
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {(["area", "bar"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setChart(t)}
              style={{
                padding:      "3px 10px",
                borderRadius: "var(--radius-sm)",
                border:       `1px solid ${chart === t ? "var(--border-default)" : "transparent"}`,
                background:   chart === t ? "rgba(255,255,255,0.05)" : "transparent",
                color:        chart === t ? "var(--text-secondary)" : "var(--text-muted)",
                fontSize:     "var(--font-size-xs)",
                cursor:       "pointer",
              }}
            >
              {t === "area" ? "Area" : "Bar"}
            </button>
          ))}
        </div>
      </div>

      {/* Gauge + breakdown */}
      {activeBucket && (
        <div style={{
          display:             "grid",
          gridTemplateColumns: "120px 1fr",
          gap:                 20,
          padding:             "12px 16px",
          borderRadius:        "var(--radius-lg)",
          border:              "1px solid var(--border-subtle)",
          background:          "rgba(255,255,255,0.015)",
        }}>
          <RiskGauge bucket={activeBucket} />
          <BucketBar bucket={activeBucket} />
        </div>
      )}

      {/* Recharts series */}
      {series.length > 0 && (
        <div style={{ height: 200 }}>
          <ResponsiveContainer width="100%" height="100%">
            {chart === "area" ? (
              <AreaChart data={series} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
                <defs>
                  {Object.entries(RISK_COLORS).map(([key, color]) => (
                    <linearGradient key={key} id={`grad-${key}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor={color} stopOpacity={0.25} />
                      <stop offset="95%" stopColor={color} stopOpacity={0.02} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#737373" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 9, fill: "#737373" }} axisLine={false} tickLine={false} />
                <Tooltip content={<RiskTooltip />} />
                {Object.entries(RISK_COLORS).map(([key, color]) => (
                  <Area
                    key={key}
                    type="monotone"
                    dataKey={key}
                    stroke={color}
                    strokeWidth={1.5}
                    fill={`url(#grad-${key})`}
                    dot={false}
                  />
                ))}
              </AreaChart>
            ) : (
              <BarChart data={series} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#737373" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 9, fill: "#737373" }} axisLine={false} tickLine={false} />
                <Tooltip content={<RiskTooltip />} />
                {Object.entries(RISK_COLORS).map(([key, color]) => (
                  <Bar key={key} dataKey={key} stackId="a" fill={color} radius={key === "critical" ? [2, 2, 0, 0] : [0, 0, 0, 0]} />
                ))}
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
