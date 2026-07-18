"use client";

import { motion } from "framer-motion";
import { CheckCircle, Circle } from "lucide-react";
import { ConnectorIcon, CONNECTOR_BRAND_COLORS } from "./ConnectorIcons";
import { dur, ease } from "@/lib/motion-tokens";
import type { Connector } from "./types";

// ─── Getting Started step ─────────────────────────────────────────────────────

interface GettingStartedStep {
  label: string;
  sublabel: string;
  done: boolean;
}

// ─── Integration Health Donut ─────────────────────────────────────────────────

function HealthDonut({
  healthy,
  issues,
  disconnected,
  total,
}: {
  healthy: number;
  issues: number;
  disconnected: number;
  total: number;
}) {
  const size = 96;
  const r = 34;
  const cx = size / 2;
  const cy = size / 2;
  const circ = 2 * Math.PI * r;

  const healthyPct    = total > 0 ? healthy    / total : 1;
  const issuePct      = total > 0 ? issues     / total : 0;
  const disconnPct    = total > 0 ? disconnected / total : 0;

  const healthyDash   = circ * healthyPct;
  const issueDash     = circ * issuePct;
  const disconnDash   = circ * disconnPct;

  // Offsets (SVG stroke starts at 3 o'clock — rotate -90 for top)
  const startAngle    = -90;
  const healthyOff    = 0;
  const issueOff      = healthyPct * 360;
  const disconnOff    = (healthyPct + issuePct) * 360;

  function segmentStyle(dashLen: number, gapLen: number, rotate: number): React.CSSProperties {
    return {
      strokeDasharray: `${dashLen} ${gapLen}`,
      strokeDashoffset: 0,
      transform: `rotate(${startAngle + rotate}deg)`,
      transformOrigin: `${cx}px ${cy}px`,
      transition: `stroke-dasharray ${dur.medium}s ${ease.out.join(",")}`,
    };
  }

  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size} style={{ overflow: "visible" }}>
        {/* Background track */}
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--border)" strokeWidth={10} />

        {/* Disconnected segment */}
        {disconnPct > 0 && (
          <circle
            cx={cx} cy={cy} r={r} fill="none"
            stroke="var(--danger)" strokeWidth={10}
            style={segmentStyle(disconnDash, circ - disconnDash, disconnOff)}
            strokeLinecap="round"
          />
        )}

        {/* Issues segment */}
        {issuePct > 0 && (
          <circle
            cx={cx} cy={cy} r={r} fill="none"
            stroke="var(--warning)" strokeWidth={10}
            style={segmentStyle(issueDash, circ - issueDash, issueOff)}
            strokeLinecap="round"
          />
        )}

        {/* Healthy segment */}
        {healthyPct > 0 && (
          <circle
            cx={cx} cy={cy} r={r} fill="none"
            stroke="var(--success)" strokeWidth={10}
            style={segmentStyle(healthyDash, circ - healthyDash, healthyOff)}
            strokeLinecap="round"
          />
        )}
      </svg>

      {/* Center text */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <p style={{ fontSize: "var(--font-size-xl)", fontWeight: 800, color: "var(--text-primary)", margin: 0, lineHeight: 1, letterSpacing: "-0.03em" }}>
          {healthy}
        </p>
        <p style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", margin: "1px 0 0", fontWeight: 500 }}>
          Healthy
        </p>
      </div>
    </div>
  );
}

// ─── ConnectorRightPanel ──────────────────────────────────────────────────────

interface ConnectorRightPanelProps {
  connectors: Connector[];
  onViewConnector: (id: string) => void;
}

export default function ConnectorRightPanel({
  connectors,
  onViewConnector,
}: ConnectorRightPanelProps) {
  // Compute health stats from live connector state
  const connected    = connectors.filter((c) => c.status === "connected" || c.status === "healthy").length;
  const issues       = connectors.filter((c) => c.status === "needs_configuration" || c.status === "connection_error").length;
  const disconnected = connectors.filter((c) => c.status === "disconnected").length;
  const total        = connectors.length;

  // "Getting Started" steps derived from live connector state
  const gettingStartedSteps: GettingStartedStep[] = [
    {
      label: "Connect your first integration",
      sublabel: connected > 0 ? `${connectors.find((c) => c.status === "connected")?.name ?? "GitHub"} connected` : "No connectors connected yet",
      done: connected > 0,
    },
    {
      label: "Add more integrations",
      sublabel: `${connected} of ${total} connected`,
      done: connected === total && total > 0,
    },
    {
      label: "Configure permissions",
      sublabel: "Set access scopes",
      done: false,
    },
    {
      label: "Run your first mission",
      sublabel: "Use integrations in missions",
      done: false,
    },
  ];

  // Popular integrations = first 5 from the connector list by id
  const popularIds = ["github", "jira", "slack", "azure-devops", "confluence"] as const;
  const popularConnectors = popularIds.map((id) => connectors.find((c) => c.id === id)).filter(Boolean) as typeof connectors;

  return (
    <aside
      aria-label="Integration panel"
      style={{
        width: 252,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-4)",
        position: "sticky",
        top: 0,
      }}
    >
      {/* ── Getting Started ── */}
      <motion.div
        initial={{ opacity: 0, x: 10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: dur.base, ease: ease.out, delay: 0.1 }}
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-md)",
          overflow: "hidden",
        }}
      >
        <div style={{ padding: "var(--space-3) var(--space-4)", borderBottom: "1px solid var(--border)" }}>
          <p style={{ fontSize: "var(--font-size-sm)", fontWeight: 700, color: "var(--text-primary)", margin: 0, letterSpacing: "-0.01em" }}>
            Getting Started
          </p>
        </div>

        <div style={{ padding: "var(--space-2) 0" }}>
          {gettingStartedSteps.map((step, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "var(--space-2)",
                padding: "var(--space-2) var(--space-4)",
              }}
            >
              {step.done ? (
                <CheckCircle size={15} style={{ color: "var(--success)", flexShrink: 0, marginTop: 1 }} />
              ) : (
                <div
                  style={{
                    width: 15,
                    height: 15,
                    borderRadius: "50%",
                    border: "1px solid var(--border-strong)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "9px",
                    fontWeight: 700,
                    color: "var(--text-muted)",
                    flexShrink: 0,
                    marginTop: 1,
                  }}
                >
                  {i + 1}
                </div>
              )}
              <div>
                <p
                  style={{
                    fontSize: "var(--font-size-xs)",
                    fontWeight: 600,
                    color: step.done ? "var(--text-secondary)" : "var(--accent-primary)",
                    margin: 0,
                    textDecoration: step.done ? "line-through" : "none",
                    textDecorationColor: "var(--text-muted)",
                  }}
                >
                  {step.label}
                </p>
                <p style={{ fontSize: 10, color: "var(--text-muted)", margin: "1px 0 0", lineHeight: 1.3 }}>
                  {step.sublabel}
                </p>
              </div>
            </div>
          ))}
        </div>
      </motion.div>

      {/* ── Popular Integrations ── */}
      <motion.div
        initial={{ opacity: 0, x: 10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: dur.base, ease: ease.out, delay: 0.15 }}
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-md)",
          overflow: "hidden",
        }}
      >
        <div style={{ padding: "var(--space-3) var(--space-4)", borderBottom: "1px solid var(--border)" }}>
          <p style={{ fontSize: "var(--font-size-sm)", fontWeight: 700, color: "var(--text-primary)", margin: 0, letterSpacing: "-0.01em" }}>
            Popular Integrations
          </p>
        </div>

        <div style={{ padding: "var(--space-2) 0" }}>
          {popularConnectors.map((c) => {
            const brand = CONNECTOR_BRAND_COLORS[c.id];
            return (
              <button
                key={c.id}
                onClick={() => onViewConnector(c.id)}
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-2)",
                  padding: "var(--space-2) var(--space-4)",
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  textAlign: "left",
                  transition: `background ${dur.snap}s ease`,
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "var(--surface-raised)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                aria-label={`View ${c.name}`}
              >
                <div
                  style={{
                    width: 26,
                    height: 26,
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
                  <ConnectorIcon id={c.id} size={13} />
                </div>
                <div style={{ minWidth: 0 }}>
                  <p style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--text-primary)", margin: 0, lineHeight: 1.2 }}>
                    {c.name}
                  </p>
                  <p style={{ fontSize: 10, color: "var(--text-muted)", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {c.description}
                  </p>
                </div>
              </button>
            );
          })}

          <div style={{ padding: "var(--space-2) var(--space-4)", paddingTop: "var(--space-1)" }}>
            <button
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                fontSize: "var(--font-size-xs)",
                fontWeight: 700,
                color: "var(--accent-primary)",
                padding: 0,
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
              aria-label="View all integrations"
            >
              View All Integrations
              <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M3 8h10M9 4l4 4-4 4" />
              </svg>
            </button>
          </div>
        </div>
      </motion.div>

      {/* ── Integration Health ── */}
      <motion.div
        initial={{ opacity: 0, x: 10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: dur.base, ease: ease.out, delay: 0.2 }}
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-md)",
          overflow: "hidden",
        }}
      >
        <div style={{ padding: "var(--space-3) var(--space-4)", borderBottom: "1px solid var(--border)" }}>
          <p style={{ fontSize: "var(--font-size-sm)", fontWeight: 700, color: "var(--text-primary)", margin: 0, letterSpacing: "-0.01em" }}>
            Integration Health
          </p>
        </div>

        <div
          style={{
            padding: "var(--space-4)",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-4)",
          }}
        >
          {/* Donut chart */}
          <HealthDonut healthy={connected} issues={issues} disconnected={disconnected} total={total} />

          {/* Legend */}
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", flex: 1 }}>
            {[
              { label: "Healthy",      count: connected,    color: "var(--success)" },
              { label: "Issues",       count: issues,       color: "var(--warning)" },
              { label: "Disconnected", count: disconnected, color: "var(--danger)" },
            ].map((item) => (
              <div key={item.label} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <span style={{ width: 7, height: 7, borderRadius: "50%", background: item.color, flexShrink: 0 }} />
                  <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-secondary)", fontWeight: 500 }}>
                    {item.label}
                  </span>
                </div>
                <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 700, color: "var(--text-primary)", fontVariantNumeric: "tabular-nums" }}>
                  {item.count}
                </span>
              </div>
            ))}
          </div>
        </div>
      </motion.div>
    </aside>
  );
}
