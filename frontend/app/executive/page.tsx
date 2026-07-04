"use client";

import { useEffect } from "react";
import { motion } from "framer-motion";
import CortexShell from "@/components/layout/CortexShell";
import AgentGraph from "@/components/runtime/AgentGraph";
import { StatusCommandBar } from "@/components/executive/StatusCommandBar";
import { MissionControl } from "@/components/executive/MissionControl";
import { LiveCognitionStream } from "@/components/executive/LiveCognitionStream";
import { SystemIntelligence, AIHealthMatrix } from "@/components/executive/SystemIntelligence";
import { AutonomyScore } from "@/components/executive/AutonomyScore";
import { ExecutiveAnalytics } from "@/components/executive/ExecutiveAnalytics";
import { useExecutiveStore } from "@/store/executiveStore";

// ── Panel wrapper ─────────────────────────────────────────────────────────

function Panel({
  title,
  children,
  style,
  headerRight,
}: {
  title?: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
  headerRight?: React.ReactNode;
}) {
  return (
    <div
      className="surface-panel"
      style={{
        display:       "flex",
        flexDirection: "column",
        gap:           0,
        overflow:      "hidden",
        ...style,
      }}
    >
      {title && (
        <div
          style={{
            display:        "flex",
            alignItems:     "center",
            justifyContent: "space-between",
            padding:        "10px 14px 8px",
            borderBottom:   "1px solid var(--border-subtle)",
            flexShrink:     0,
          }}
        >
          <span
            style={{
              fontSize:      "var(--font-size-xs)",
              fontWeight:    700,
              color:         "var(--text-muted)",
              letterSpacing: "0.07em",
              textTransform: "uppercase",
            }}
          >
            {title}
          </span>
          {headerRight}
        </div>
      )}
      <div style={{ flex: 1, overflow: "hidden", padding: "12px 14px" }}>
        {children}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function ExecutivePage() {
  const lastRefresh = useExecutiveStore((s) => s.lastRefresh);

  useEffect(() => {
    void useExecutiveStore.getState().refreshAll();
    const id = setInterval(() => {
      void useExecutiveStore.getState().refreshAll();
    }, 15000);
    return () => clearInterval(id);
  }, []);

  const refreshTime = lastRefresh
    ? new Date(lastRefresh).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : null;

  return (
    <CortexShell title="Executive">
      {/* Deep gradient background */}
      <div
        style={{
          position:   "fixed",
          inset:      0,
          background: "radial-gradient(ellipse at 20% 10%, rgba(130,192,164,0.06) 0%, transparent 50%), radial-gradient(ellipse at 80% 80%, rgba(124,58,237,0.04) 0%, transparent 50%)",
          pointerEvents: "none",
          zIndex:     0,
        }}
      />

      {/* Page content */}
      <div
        style={{
          display:       "flex",
          flexDirection: "column",
          gap:           0,
          height:        "100%",
          position:      "relative",
          zIndex:        1,
          overflowY:     "auto",
        }}
        className="cortex-scroll"
      >
        {/* Page header */}
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          style={{
            display:        "flex",
            alignItems:     "baseline",
            gap:            10,
            padding:        "16px 20px 10px",
            flexShrink:     0,
          }}
        >
          <h1 style={{ margin: 0, fontSize: "var(--font-size-2xl)", fontWeight: 900, color: "var(--text-primary)", letterSpacing: "-0.02em" }}>
            CortexPrime
          </h1>
          <span style={{ fontSize: "var(--font-size-sm)", color: "var(--text-muted)", fontStyle: "italic" }}>
            Autonomous Intelligence Platform
          </span>
          {refreshTime && (
            <span className="label-mono" style={{ marginLeft: "auto", fontSize: "10px", color: "var(--text-muted)" }}>
              Updated {refreshTime}
            </span>
          )}
        </motion.div>

        {/* Row 1 — Status command bar */}
        <div style={{ padding: "0 20px", flexShrink: 0 }}>
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="surface-panel"
            style={{ padding: "10px 14px" }}
          >
            <StatusCommandBar />
          </motion.div>
        </div>

        {/* Row 2 — Live Cognition Stream | Mission Control */}
        <div
          style={{
            display:   "flex",
            gap:       12,
            padding:   "12px 20px 0",
            flexShrink: 0,
            minHeight: 260,
          }}
        >
          <motion.div
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 }}
            style={{ width: 280, flexShrink: 0 }}
          >
            <Panel title="Live Cognition" style={{ height: "100%" }}>
              <LiveCognitionStream />
            </Panel>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 }}
            style={{ flex: 1, minWidth: 0 }}
          >
            <Panel title="Mission Control" style={{ height: "100%" }}>
              <MissionControl />
            </Panel>
          </motion.div>
        </div>

        {/* Row 3 — Agent Graph | System Intelligence + Health Matrix */}
        <div
          style={{
            display:   "flex",
            gap:       12,
            padding:   "12px 20px 0",
            flexShrink: 0,
            minHeight: 340,
          }}
        >
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            style={{ flex: "0 0 55%" }}
          >
            <Panel title="Agent Graph" style={{ height: "100%" }}>
              <div style={{ height: 280 }}>
                <AgentGraph />
              </div>
            </Panel>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 12 }}
          >
            <Panel title="System Intelligence" style={{ flex: "0 0 auto" }}>
              <SystemIntelligence />
            </Panel>
            <Panel title="AI Health Matrix" style={{ flex: 1 }}>
              <AIHealthMatrix />
            </Panel>
          </motion.div>
        </div>

        {/* Row 4 — Autonomy Score | Executive Analytics */}
        <div
          style={{
            display:   "flex",
            gap:       12,
            padding:   "12px 20px 20px",
            flexShrink: 0,
          }}
        >
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            style={{ width: 300, flexShrink: 0 }}
          >
            <Panel title="Autonomy Score" style={{ minHeight: 320 }}>
              <AutonomyScore />
            </Panel>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            style={{ flex: 1, minWidth: 0 }}
          >
            <Panel title="Executive Analytics" style={{ minHeight: 320 }}>
              <ExecutiveAnalytics />
            </Panel>
          </motion.div>
        </div>
      </div>
    </CortexShell>
  );
}
