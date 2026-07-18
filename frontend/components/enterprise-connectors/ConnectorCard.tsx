"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Plug } from "lucide-react";
import { dur, ease } from "@/lib/motion-tokens";
import { ConnectorIcon, CONNECTOR_BRAND_COLORS } from "./ConnectorIcons";
import type { Connector, ConnectorStatus } from "./types";

// ─── Status config ────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<
  ConnectorStatus,
  { label: string; dot: string; bg: string; text: string; border: string; pulse: boolean }
> = {
  connected:          { label: "Connected",          dot: "var(--success)",   bg: "var(--success-muted)",   text: "var(--success)",   border: "var(--success-border)", pulse: true },
  disconnected:       { label: "Disconnected",       dot: "var(--text-muted)",bg: "var(--surface-raised)",  text: "var(--text-muted)", border: "var(--border)",         pulse: false },
  healthy:            { label: "Healthy",            dot: "var(--success)",   bg: "var(--success-muted)",   text: "var(--success)",   border: "var(--success-border)", pulse: true },
  needs_configuration:{ label: "Needs Config",       dot: "var(--warning)",   bg: "var(--warning-muted)",   text: "var(--warning)",   border: "var(--warning-border)", pulse: false },
  connection_error:   { label: "Connection Error",   dot: "var(--danger)",    bg: "var(--danger-muted)",    text: "var(--danger)",    border: "var(--danger-border)", pulse: false },
};

// ─── Status dot ───────────────────────────────────────────────────────────────

function PulseDot({ color, pulse }: { color: string; pulse: boolean }) {
  return (
    <span style={{ position: "relative", display: "inline-flex", alignItems: "center", justifyContent: "center", width: 8, height: 8, flexShrink: 0 }}>
      {pulse && (
        <motion.span
          animate={{ scale: [1, 1.8, 1], opacity: [0.5, 0, 0.5] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
          style={{ position: "absolute", inset: 0, borderRadius: "50%", background: color }}
        />
      )}
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: color, flexShrink: 0, position: "relative" }} />
    </span>
  );
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface ConnectorCardProps {
  connector: Connector;
  onConnect: (id: string) => void;
  onViewDetails: (id: string) => void;
}

// ─── ConnectorCard ────────────────────────────────────────────────────────────

export default function ConnectorCard({ connector, onConnect, onViewDetails }: ConnectorCardProps) {
  const [hovered, setHovered] = useState(false);
  const statusCfg = STATUS_CONFIG[connector.status];
  const brand = CONNECTOR_BRAND_COLORS[connector.id];
  const isConnected = connector.status === "connected" || connector.status === "healthy";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: dur.base, ease: ease.out }}
      onHoverStart={() => setHovered(true)}
      onHoverEnd={() => setHovered(false)}
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-md)",
        boxShadow: hovered ? "var(--shadow-sm)" : "var(--shadow-xs)",
        display: "flex",
        flexDirection: "column",
        cursor: "default",
        transition: `border-color ${dur.fast}s ease, box-shadow ${dur.fast}s ease, transform ${dur.fast}s ease`,
        transform: hovered ? "translateY(-2px)" : "translateY(0)",
        overflow: "hidden",
        position: "relative",
      }}
      role="article"
      aria-label={`${connector.name} — ${statusCfg.label}`}
    >
      {/* ── Card body ── */}
      <div style={{ padding: "var(--space-4)", display: "flex", flexDirection: "column", gap: "var(--space-4)", flex: 1 }}>

        {/* Header row: icon + name + status */}
        <div style={{ display: "flex", alignItems: "flex-start", gap: "var(--space-2)", justifyContent: "space-between" }}>
          {/* Brand icon and name */}
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", minWidth: 0, flex: 1 }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: "var(--radius-sm)",
                background: brand.bg,
                border: `1px solid ${brand.border}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: brand.text,
                flexShrink: 0,
              }}
            >
              <ConnectorIcon id={connector.id} size={16} />
            </div>

            <div style={{ minWidth: 0 }}>
              <p
                style={{
                  fontSize: "var(--font-size-base)",
                  fontWeight: 700,
                  color: "var(--text-primary)",
                  margin: 0,
                  lineHeight: 1.2,
                  letterSpacing: "-0.01em",
                }}
              >
                {connector.name}
              </p>
              <p
                style={{
                  fontSize: 10,
                  color: "var(--text-muted)",
                  margin: 0,
                  lineHeight: 1.2,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {connector.description}
              </p>
            </div>
          </div>

          {/* Status badge */}
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "2px 6px",
              borderRadius: "var(--radius-pill)",
              fontSize: 9,
              fontWeight: 700,
              background: statusCfg.bg,
              color: statusCfg.text,
              border: `1px solid ${statusCfg.border}`,
              whiteSpace: "nowrap",
              letterSpacing: "0.02em",
              flexShrink: 0,
            }}
          >
            <PulseDot color={statusCfg.dot} pulse={statusCfg.pulse} />
            {statusCfg.label}
          </span>
        </div>

        {/* ── Connected state: stats grid ── */}
        {isConnected && connector.stats && connector.stats.length > 0 ? (
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: "var(--space-2)",
              padding: "0 var(--space-1)",
            }}
          >
            {connector.stats.slice(0, 3).map((stat) => (
              <div key={stat.label} style={{ flex: 1 }}>
                <p style={{ fontSize: 10, color: "var(--text-muted)", margin: 0, fontWeight: 500, lineHeight: 1.2 }}>
                  {stat.label}
                </p>
                <p
                  style={{
                    fontSize: "var(--font-size-md)",
                    fontWeight: 700,
                    color: "var(--text-primary)",
                    margin: "2px 0 0",
                    lineHeight: 1.1,
                    letterSpacing: "-0.02em",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {stat.value}
                </p>
              </div>
            ))}
          </div>
        ) : !isConnected ? (
          /* ── Disconnected empty state ── */
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              textAlign: "center",
              padding: "var(--space-4) 0",
              gap: "var(--space-2)",
              flex: 1,
            }}
          >
            {/* Connector illustration */}
            <div style={{ display: "flex", alignItems: "center", gap: 6, opacity: 0.4 }}>
              <div style={{ width: 28, height: 28, borderRadius: "var(--radius-sm)", background: "var(--surface-raised)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <ConnectorIcon id={connector.id} size={14} />
              </div>
              <div style={{ display: "flex", gap: 2 }}>
                {[0, 1, 2].map((i) => (
                  <div key={i} style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--border-strong)" }} />
                ))}
              </div>
              <div style={{ width: 28, height: 28, borderRadius: "var(--radius-sm)", background: "var(--surface-raised)", border: "1px dashed var(--border-strong)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Plug size={12} style={{ color: "var(--text-muted)" }} />
              </div>
            </div>
            <p style={{ fontSize: 10, color: "var(--text-muted)", margin: 0, lineHeight: 1.4, maxWidth: 170 }}>
              Connect your {connector.name} instance to start syncing data
            </p>
          </div>
        ) : null}

        {/* ── Latency + Last Sync (connected only) ── */}
        {isConnected && (
          <div style={{ display: "flex", gap: "var(--space-4)", padding: "0 var(--space-1)" }}>
            <div style={{ flex: 1 }}>
              <p style={{ fontSize: 10, color: "var(--text-muted)", margin: 0, fontWeight: 500 }}>
                Latency
              </p>
              <p style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--text-secondary)", margin: "1px 0 0" }}>
                {connector.latency || "--"}
              </p>
            </div>
            <div style={{ flex: 1 }}>
              <p style={{ fontSize: 10, color: "var(--text-muted)", margin: 0, fontWeight: 500 }}>
                Last Sync
              </p>
              <p style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--text-secondary)", margin: "1px 0 0", display: "inline-flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--success)", display: "inline-block" }} />
                {connector.lastSync || "--"}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* ── Card footer ── */}
      <div
        style={{
          borderTop: "1px solid var(--border)",
          padding: "12px var(--space-4)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {isConnected ? (
          <motion.button
            whileHover={{ x: 2 }}
            onClick={() => onViewDetails(connector.id)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              fontSize: "var(--font-size-xs)",
              fontWeight: 700,
              color: "var(--accent-primary)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 4,
              padding: 0,
              letterSpacing: "-0.005em",
            }}
            aria-label={`Manage ${connector.name} integration`}
          >
            Manage Integration
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M3 8h10M9 4l4 4-4 4" />
            </svg>
          </motion.button>
        ) : (
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => onConnect(connector.id)}
            style={{
              width: "100%",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 5,
              padding: "7px 12px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border)",
              background: "var(--surface)",
              color: "var(--accent-primary)",
              fontSize: "var(--font-size-xs)",
              fontWeight: 700,
              cursor: "pointer",
              letterSpacing: "-0.005em",
              boxShadow: "var(--shadow-xs)",
            }}
            aria-label={`Connect ${connector.name}`}
          >
            Connect Now
          </motion.button>
        )}
      </div>
    </motion.div>
  );
}
