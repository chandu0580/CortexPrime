"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Info,
  Key,
  Activity,
  ShieldCheck,
  Clock,
  Settings,
  BarChart3,
} from "lucide-react";
import { dur, ease } from "@/lib/motion-tokens";
import { ConnectorIcon, CONNECTOR_BRAND_COLORS } from "./ConnectorIcons";
import ConnectorOverview from "./ConnectorOverview";
import ConnectorAuthentication from "./ConnectorAuthentication";
import ConnectorHealth from "./ConnectorHealth";
import ConnectorPermissions from "./ConnectorPermissions";
import ConnectorActivity from "./ConnectorActivity";
import ConnectorSettings from "./ConnectorSettings";
import ConnectorAnalytics from "./ConnectorAnalytics";
import type { Connector, ConnectorStatus } from "./types";

// ─── Types ───────────────────────────────────────────────────────────────────

type TabId =
  | "overview"
  | "authentication"
  | "analytics"
  | "health"
  | "permissions"
  | "activity"
  | "settings";

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: "overview",        label: "Overview",        icon: <Info size={14} /> },
  { id: "authentication",  label: "Auth",             icon: <Key size={14} /> },
  { id: "analytics",       label: "Analytics",        icon: <BarChart3 size={14} /> },
  { id: "health",          label: "Health",           icon: <Activity size={14} /> },
  { id: "permissions",     label: "Permissions",      icon: <ShieldCheck size={14} /> },
  { id: "activity",        label: "Activity",         icon: <Clock size={14} /> },
  { id: "settings",        label: "Settings",         icon: <Settings size={14} /> },
];

const STATUS_LABELS: Record<ConnectorStatus, { label: string; dot: string; bg: string; text: string; border: string }> = {
  connected:          { label: "Connected",          dot: "var(--success)",   bg: "var(--success-muted)",   text: "var(--success)",   border: "var(--success-border)" },
  disconnected:       { label: "Disconnected",       dot: "var(--danger)",    bg: "var(--danger-muted)",    text: "var(--danger)",    border: "var(--danger-border)" },
  healthy:            { label: "Healthy",            dot: "var(--success)",   bg: "var(--success-muted)",   text: "var(--success)",   border: "var(--success-border)" },
  needs_configuration:{ label: "Needs Config",       dot: "var(--warning)",   bg: "var(--warning-muted)",   text: "var(--warning)",   border: "rgba(249,168,37,0.32)" },
  connection_error:   { label: "Connection Error",   dot: "var(--danger)",    bg: "var(--danger-muted)",    text: "var(--danger)",    border: "var(--danger-border)" },
};

// ─── Props ────────────────────────────────────────────────────────────────────

interface ConnectorDrawerProps {
  connector: Connector | null;
  open: boolean;
  onClose: () => void;
  onConnect: (id: string) => void;
  onDisconnect?: (id: string) => void;
  onRefresh?: () => void;
}

// ─── ConnectorDrawer ─────────────────────────────────────────────────────────

export default function ConnectorDrawer({
  connector,
  open,
  onClose,
  onConnect,
  onDisconnect,
  onRefresh,
}: ConnectorDrawerProps) {
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const tabRefs = useRef<Record<TabId, HTMLButtonElement | null>>({} as Record<TabId, HTMLButtonElement | null>);

  // Reset to overview when a new connector opens
  useEffect(() => {
    if (open) setActiveTab("overview");
  }, [open, connector?.id]);

  // Keyboard escape
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && open) onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  // Arrow key navigation between tabs
  function handleTabKeyDown(e: React.KeyboardEvent, currentId: TabId) {
    const idx = TABS.findIndex((t) => t.id === currentId);
    if (e.key === "ArrowDown" || e.key === "ArrowRight") {
      e.preventDefault();
      const next = TABS[(idx + 1) % TABS.length];
      setActiveTab(next.id);
      tabRefs.current[next.id]?.focus();
    } else if (e.key === "ArrowUp" || e.key === "ArrowLeft") {
      e.preventDefault();
      const prev = TABS[(idx - 1 + TABS.length) % TABS.length];
      setActiveTab(prev.id);
      tabRefs.current[prev.id]?.focus();
    }
  }

  return (
    <AnimatePresence>
      {open && connector && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: dur.fast }}
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.45)",
              backdropFilter: "blur(3px)",
              zIndex: 100,
            }}
            onClick={onClose}
            aria-hidden="true"
          />

          {/* Drawer panel */}
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 32, mass: 0.85 }}
            style={{
              position: "fixed",
              top: 0,
              right: 0,
              bottom: 0,
              width: "90vw",
              maxWidth: 520,
              background: "var(--surface)",
              borderLeft: "1px solid var(--border)",
              boxShadow: "var(--shadow-xl)",
              zIndex: 101,
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
            role="dialog"
            aria-modal="true"
            aria-label={`${connector.name} connector details`}
          >
            {/* ── Drawer header ── */}
            <DrawerHeader connector={connector} onClose={onClose} />

            {/* ── Body (tabs + content) ── */}
            <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
              {/* Vertical tab nav */}
              <nav
                style={{
                  width: 130,
                  flexShrink: 0,
                  borderRight: "1px solid var(--border)",
                  padding: "var(--space-3) var(--space-2)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 2,
                  overflowY: "auto",
                  background: "var(--surface-raised)",
                }}
                aria-label="Connector sections"
                role="tablist"
                aria-orientation="vertical"
              >
                {TABS.map((tab) => {
                  const isActive = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      ref={(el) => { tabRefs.current[tab.id] = el; }}
                      role="tab"
                      aria-selected={isActive}
                      aria-controls={`tabpanel-${tab.id}`}
                      id={`tab-${tab.id}`}
                      onClick={() => setActiveTab(tab.id)}
                      onKeyDown={(e) => handleTabKeyDown(e, tab.id)}
                      tabIndex={isActive ? 0 : -1}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        padding: "8px 10px",
                        borderRadius: "var(--radius-sm)",
                        border: isActive ? "1px solid var(--accent-border)" : "1px solid transparent",
                        background: isActive ? "var(--accent-muted)" : "transparent",
                        color: isActive ? "var(--accent-primary)" : "var(--text-secondary)",
                        fontSize: "var(--font-size-xs)",
                        fontWeight: isActive ? 700 : 500,
                        cursor: "pointer",
                        textAlign: "left",
                        width: "100%",
                        transition: `all ${dur.fast}s ease`,
                        letterSpacing: "-0.005em",
                        outline: "none",
                      }}
                      onMouseEnter={(e) => {
                        if (!isActive) {
                          e.currentTarget.style.background = "var(--surface-overlay)";
                          e.currentTarget.style.color = "var(--text-primary)";
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!isActive) {
                          e.currentTarget.style.background = "transparent";
                          e.currentTarget.style.color = "var(--text-secondary)";
                        }
                      }}
                      onFocus={(e) => {
                        if (!isActive) {
                          e.currentTarget.style.outline = "2px solid var(--accent-primary)";
                          e.currentTarget.style.outlineOffset = "1px";
                        }
                      }}
                      onBlur={(e) => {
                        e.currentTarget.style.outline = "none";
                      }}
                    >
                      {tab.icon}
                      {tab.label}
                    </button>
                  );
                })}
              </nav>

              {/* Tab content */}
              <div
                style={{ flex: 1, overflowY: "auto", padding: "var(--space-6)" }}
                role="tabpanel"
                id={`tabpanel-${activeTab}`}
                aria-labelledby={`tab-${activeTab}`}
              >
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeTab}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: dur.fast, ease: ease.out }}
                  >
                    {activeTab === "overview" && (
                      <ConnectorOverview
                        connector={connector}
                        onConnect={() => setActiveTab("authentication")}
                        onDisconnect={() => {
                          onDisconnect?.(connector.id);
                          onRefresh?.();
                        }}
                      />
                    )}
                    {activeTab === "authentication" && (
                      <ConnectorAuthentication
                        connector={connector}
                        onConnected={() => { onRefresh?.(); setActiveTab("overview"); }}
                      />
                    )}
                    {activeTab === "analytics" && (
                      <ConnectorAnalytics connector={connector} />
                    )}
                    {activeTab === "health" && (
                      <ConnectorHealth connector={connector} />
                    )}
                    {activeTab === "permissions" && (
                      <ConnectorPermissions connector={connector} />
                    )}
                    {activeTab === "activity" && (
                      <ConnectorActivity connector={connector} />
                    )}
                    {activeTab === "settings" && (
                      <ConnectorSettings connector={connector} />
                    )}
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

// ─── DrawerHeader sub-component ──────────────────────────────────────────────

function DrawerHeader({
  connector,
  onClose,
}: {
  connector: Connector;
  onClose: () => void;
}) {
  const brand = CONNECTOR_BRAND_COLORS[connector.id];
  const status = STATUS_LABELS[connector.status];

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "var(--space-4) var(--space-5)",
        borderBottom: "1px solid var(--border)",
        flexShrink: 0,
        background: "var(--surface)",
        gap: "var(--space-3)",
      }}
    >
      {/* Left: icon + name + badge */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", minWidth: 0 }}>
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: "var(--radius-md)",
            background: brand.bg,
            border: `1px solid ${brand.border}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: brand.text,
            flexShrink: 0,
          }}
        >
          <ConnectorIcon id={connector.id} size={20} />
        </div>

        <div style={{ minWidth: 0 }}>
          <p
            style={{
              fontSize: "var(--font-size-xs)",
              fontWeight: 600,
              color: "var(--text-muted)",
              margin: 0,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
            }}
          >
            Connector
          </p>
          <h2
            style={{
              fontSize: "var(--font-size-lg)",
              fontWeight: 700,
              color: "var(--text-primary)",
              margin: "1px 0 4px",
              letterSpacing: "-0.02em",
              lineHeight: 1.2,
            }}
          >
            {connector.name}
          </h2>
          {/* Status badge */}
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              padding: "2px 8px",
              borderRadius: "var(--radius-pill)",
              fontSize: "var(--font-size-xs)",
              fontWeight: 600,
              background: status.bg,
              color: status.text,
              border: `1px solid ${status.border}`,
            }}
          >
            <span
              style={{
                width: 5,
                height: 5,
                borderRadius: "50%",
                background: status.dot,
                flexShrink: 0,
              }}
            />
            {status.label}
          </span>
        </div>
      </div>

      {/* Close button */}
      <button
        onClick={onClose}
        aria-label="Close connector panel"
        style={{
          width: 32,
          height: 32,
          borderRadius: "var(--radius-sm)",
          border: "1px solid var(--border)",
          background: "transparent",
          color: "var(--text-muted)",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          transition: `color ${dur.fast}s ease, border-color ${dur.fast}s ease, background ${dur.fast}s ease`,
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = "var(--text-primary)";
          e.currentTarget.style.borderColor = "var(--border-strong)";
          e.currentTarget.style.background = "var(--surface-raised)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.color = "var(--text-muted)";
          e.currentTarget.style.borderColor = "var(--border)";
          e.currentTarget.style.background = "transparent";
        }}
      >
        <X size={16} />
      </button>
    </div>
  );
}
