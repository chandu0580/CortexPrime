"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Activity, Wifi, Zap, BarChart2, Clock, RefreshCw, Shield, Database, Loader2 } from "lucide-react";
import { dur, ease } from "@/lib/motion-tokens";
import type { Connector } from "./types";
import { getConnectorHealth } from "@/services/connector-api";
import type { ConnectorHealthDetail } from "@/services/connector-api";

interface ConnectorHealthProps {
  connector: Connector;
}

type HealthStatus = "success" | "warning" | "error" | "neutral";

interface HealthRow {
  label: string;
  value: string;
  status: HealthStatus;
  icon: React.ReactNode;
}

const STATUS_STYLE: Record<HealthStatus, { dot: string; text: string }> = {
  success: { dot: "var(--success)",   text: "var(--success)" },
  warning: { dot: "var(--warning)",   text: "var(--warning)" },
  error:   { dot: "var(--danger)",    text: "var(--danger)" },
  neutral: { dot: "var(--text-muted)", text: "var(--text-muted)" },
};

function HealthRow({ row, index }: { row: HealthRow; index: number }) {
  const colors = STATUS_STYLE[row.status];
  const isPlaceholder = row.value === "--";

  return (
    <motion.div
      initial={{ opacity: 0, x: -4 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: dur.fast, ease: ease.out, delay: index * 0.04 }}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "11px 14px",
        background: index % 2 === 0 ? "var(--surface)" : "var(--surface-raised)",
        borderBottom: "1px solid var(--border)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ color: "var(--text-muted)", display: "flex", alignItems: "center" }}>
          {row.icon}
        </span>
        <span style={{ fontSize: "var(--font-size-sm)", color: "var(--text-secondary)", fontWeight: 500 }}>
          {row.label}
        </span>
      </div>

      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          fontSize: "var(--font-size-sm)",
          color: isPlaceholder ? "var(--text-muted)" : colors.text,
          fontWeight: 600,
          fontVariantNumeric: "tabular-nums",
          letterSpacing: "-0.01em",
        }}
      >
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: isPlaceholder ? "var(--border-strong)" : colors.dot,
            flexShrink: 0,
          }}
        />
        {row.value}
      </span>
    </motion.div>
  );
}

function HealthSection({ title, rows, startIndex }: { title: string; rows: HealthRow[]; startIndex: number }) {
  return (
    <div>
      <p style={{
        fontSize: "var(--font-size-label)", fontWeight: 700, color: "var(--text-primary)",
        margin: "0 0 var(--space-2)", letterSpacing: "0.04em", textTransform: "uppercase",
      }}>
        {title}
      </p>
      <div style={{ borderRadius: "var(--radius-sm)", border: "1px solid var(--border)", overflow: "hidden" }}>
        {rows.map((row, i) => (
          <HealthRow key={row.label} row={row} index={startIndex + i} />
        ))}
      </div>
    </div>
  );
}

export default function ConnectorHealth({ connector }: ConnectorHealthProps) {
  const [health, setHealth] = useState<ConnectorHealthDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const isConnected = connector.status === "connected" || connector.status === "healthy";

  useEffect(() => {
    if (!isConnected) return;
    setLoading(true);
    getConnectorHealth(connector.id)
      .then(setHealth)
      .catch(() => setHealth(null))
      .finally(() => setLoading(false));
  }, [connector.id, isConnected]);

  const healthStatus: HealthStatus = !isConnected ? "neutral"
    : loading ? "neutral"
    : health?.status === "healthy" ? "success"
    : health?.status === "unavailable" ? "error"
    : "neutral";

  const connectionRows: HealthRow[] = [
    {
      label: "Connection Status",
      value: loading ? "Loading..." : isConnected ? "Connected" : "--",
      status: loading ? "neutral" : isConnected ? "success" : "neutral",
      icon: <Wifi size={13} />,
    },
    {
      label: "Authentication",
      value: loading ? "..." : health?.authenticated ? "Verified" : isConnected ? "Verified" : "--",
      status: loading ? "neutral" : health?.authenticated ? "success" : "neutral",
      icon: <Shield size={13} />,
    },
    {
      label: "API Health",
      value: loading ? "..." : health?.status === "healthy" ? "Healthy" : health?.status || "--",
      status: healthStatus,
      icon: <Activity size={13} />,
    },
  ];

  const performanceRows: HealthRow[] = [
    {
      label: "Latency",
      value: health?.latency_ms != null ? `${health.latency_ms} ms` : "--",
      status: health?.latency_ms != null && health.latency_ms < 500 ? "success" : health?.latency_ms != null ? "warning" : "neutral",
      icon: <Zap size={13} />,
    },
    {
      label: "Rate Limits",
      value: health?.rate_limits ? "Available" : "--",
      status: health?.rate_limits ? "success" : "neutral",
      icon: <BarChart2 size={13} />,
    },
    {
      label: "Available Operations",
      value: health?.available_operations?.length != null ? String(health.available_operations.length) : "--",
      status: health?.available_operations?.length ? "success" : "neutral",
      icon: <RefreshCw size={13} />,
    },
  ];

  const usageRows: HealthRow[] = [
    {
      label: "Last Sync",
      value: health?.last_sync || "--",
      status: health?.last_sync ? "success" : "neutral",
      icon: <Clock size={13} />,
    },
    {
      label: "Auth Type",
      value: health?.authentication_type || "--",
      status: health?.authentication_type ? "success" : "neutral",
      icon: <Database size={13} />,
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <div style={{
        display: "flex", alignItems: "center", gap: "var(--space-2)",
        paddingBottom: "var(--space-4)", borderBottom: "1px solid var(--border)",
      }}>
        <div style={{
          width: 32, height: 32, borderRadius: "var(--radius-sm)",
          background: "var(--accent-muted)", display: "flex", alignItems: "center",
          justifyContent: "center", color: "var(--accent-primary)",
        }}>
          {loading ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Activity size={16} />}
        </div>
        <div>
          <p style={{ fontSize: "var(--font-size-sm)", fontWeight: 700, color: "var(--text-primary)", margin: 0, letterSpacing: "-0.01em" }}>
            Health Monitor
          </p>
          <p style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", margin: 0 }}>
            {isConnected ? "Live metrics from backend" : "Connect to view health data"}
          </p>
        </div>
      </div>

      <HealthSection title="Connection" rows={connectionRows} startIndex={0} />
      <HealthSection title="Performance" rows={performanceRows} startIndex={3} />
      <HealthSection title="Usage" rows={usageRows} startIndex={6} />
    </div>
  );
}
