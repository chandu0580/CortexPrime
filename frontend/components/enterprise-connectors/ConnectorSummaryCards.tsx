"use client";

import { motion } from "framer-motion";
import { Link as LinkIcon, Heart, ShieldAlert, Activity, BarChart2 } from "lucide-react";
import { dur } from "@/lib/motion-tokens";

// ─── Spark line SVG (smooth solid wavy line) ─────────────────────────────────

function SparkLine({ color = "var(--accent-primary)" }: { color?: string }) {
  return (
    <svg width="70" height="26" viewBox="0 0 70 26" fill="none" aria-hidden="true">
      <path
        d="M2 18 L12 10 L22 15 L32 6 L42 11 L52 4 L68 9"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ─── Individual card ─────────────────────────────────────────────────────────

interface CardConfig {
  icon: React.ReactNode;
  label: string;
  sublabel: string;
  value: string;
  accentBg: string;
  accentText: string;
  accentBorder: string;
  showSparkline?: boolean;
  index: number;
}

function SummaryCard({ icon, label, sublabel, value, accentBg, accentText, accentBorder, showSparkline, index }: CardConfig) {
  const isEmpty = value === "--" || !value;
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.06 }}
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-md)",
        boxShadow: "var(--shadow-xs)",
        padding: "var(--space-4)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-1)",
        position: "relative",
        overflow: "hidden",
        justifyContent: "space-between",
        minHeight: "110px",
      }}
    >
      {/* Top row: Label on left, Icon/Sparkline on right */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "var(--space-2)" }}>
        <p style={{ 
          fontSize: "var(--font-size-xs)", 
          fontWeight: 600, 
          color: "var(--text-muted)", 
          margin: 0, 
          letterSpacing: "-0.01em" 
        }}>
          {label}
        </p>

        {showSparkline && !isEmpty ? (
          <div style={{ paddingRight: "4px" }}>
            <SparkLine color={accentText} />
          </div>
        ) : (
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: "50%",
              background: accentBg,
              border: `1px solid ${accentBorder}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: accentText,
              flexShrink: 0,
            }}
          >
            {icon}
          </div>
        )}
      </div>

      {/* Middle row: Large Value */}
      <div style={{ marginTop: "auto" }}>
        <p
          style={{
            fontSize: "var(--font-size-2xl)",
            fontWeight: 800,
            color: isEmpty ? "var(--text-muted)" : "var(--text-primary)",
            margin: 0,
            lineHeight: 1.1,
            letterSpacing: "-0.03em",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {value}
        </p>
        <p style={{ 
          fontSize: "11px", 
          color: "var(--text-muted)", 
          margin: "3px 0 0",
          lineHeight: 1.2
        }}>
          {sublabel}
        </p>
      </div>
    </motion.div>
  );
}

// ─── Props ────────────────────────────────────────────────────────────────────

export interface ConnectorSummaryData {
  connected: number | null;
  healthy: number | null;
  pending: number | null;
  lastSync: string | null;
  apiCallsToday?: number | null;
  avgLatency?: string | null;
  errorsToday?: number | null;
  total?: number | null;
}

interface ConnectorSummaryCardsProps {
  data?: ConnectorSummaryData;
}

// ─── ConnectorSummaryCards ────────────────────────────────────────────────────

export default function ConnectorSummaryCards({ data }: ConnectorSummaryCardsProps) {
  const total      = data?.total      ?? null;
  const connected  = data?.connected  ?? null;
  const healthy    = data?.healthy    ?? null;
  const apiCalls   = data?.apiCallsToday ?? null;
  const avgLatency = data?.avgLatency ?? null;
  const errors     = data?.errorsToday ?? null;

  const connectedVal = connected != null
    ? (total != null ? `${connected} / ${total}` : String(connected))
    : "--";

  const cards: Omit<CardConfig, "index">[] = [
    {
      icon: <LinkIcon size={15} />,
      label: "Connected",
      sublabel: "Integrations active",
      value: connectedVal,
      accentBg: "var(--success-muted)",
      accentText: "var(--success)",
      accentBorder: "var(--success-border)",
      showSparkline: false,
    },
    {
      icon: <Heart size={15} fill="currentColor" style={{ opacity: 0.85 }} />,
      label: "Healthy",
      sublabel: "All systems operational",
      value: healthy != null ? String(healthy) : "--",
      accentBg: "var(--success-muted)",
      accentText: "var(--success)",
      accentBorder: "var(--success-border)",
      showSparkline: false,
    },
    {
      icon: <Activity size={15} />,
      label: "API Calls (Today)",
      sublabel: "Across all integrations",
      value: apiCalls != null ? apiCalls.toLocaleString() : "--",
      accentBg: "var(--accent-muted)",
      accentText: "var(--accent-primary)",
      accentBorder: "var(--accent-border)",
      showSparkline: true,
    },
    {
      icon: <BarChart2 size={15} />,
      label: "Avg. Latency",
      sublabel: "Across all integrations",
      value: avgLatency ?? "--",
      accentBg: "rgba(124, 58, 237, 0.08)",
      accentText: "var(--violet)",
      accentBorder: "rgba(124, 58, 237, 0.2)",
      showSparkline: true,
    },
    {
      icon: <ShieldAlert size={15} />,
      label: "Errors (Today)",
      sublabel: "No critical errors",
      value: errors != null ? String(errors) : "--",
      accentBg: "var(--danger-muted)",
      accentText: "var(--danger)",
      accentBorder: "var(--danger-border)",
      showSparkline: false,
    },
  ];

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(5, 1fr)",
        gap: "var(--space-3)",
      }}
    >
      {cards.map((card, i) => (
        <SummaryCard key={card.label} {...card} index={i} />
      ))}
    </div>
  );
}
