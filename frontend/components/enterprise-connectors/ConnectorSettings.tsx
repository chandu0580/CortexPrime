"use client";

import { useState, useCallback, useEffect } from "react";
import { motion } from "framer-motion";
import { Settings, Check } from "lucide-react";
import { dur } from "@/lib/motion-tokens";
import type { Connector } from "./types";

interface ConnectorSettingsProps {
  connector: Connector;
}

interface ToggleItem {
  key: string;
  label: string;
  description: string;
  group: string;
}

const TOGGLES: ToggleItem[] = [
  {
    key: "ai_access",
    label: "Allow AI Agent Access",
    description: "Permit CortexPrime AI Agents to perform operations through this connector.",
    group: "Access Control",
  },
  {
    key: "mission_access",
    label: "Mission Access",
    description: "Allow this connector to be used in active missions and workflows.",
    group: "Access Control",
  },
  {
    key: "auto_reconnect",
    label: "Auto Reconnect",
    description: "Automatically attempt to reconnect if the connection is lost.",
    group: "Reliability",
  },
  {
    key: "health_monitoring",
    label: "Health Monitoring",
    description: "Enable proactive health checks and alerting for this connector.",
    group: "Reliability",
  },
  {
    key: "notifications",
    label: "Notifications",
    description: "Receive notifications for connection events, errors, and sync status.",
    group: "Alerts",
  },
];

const SETTINGS_STORAGE_KEY = "cortexprime_connector_settings";

function loadSettings(connectorId: string): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(`${SETTINGS_STORAGE_KEY}_${connectorId}`);
    if (raw) return JSON.parse(raw);
  } catch {}
  return {
    ai_access: true,
    mission_access: false,
    auto_reconnect: true,
    health_monitoring: true,
    notifications: true,
  };
}

function saveSettings(connectorId: string, settings: Record<string, boolean>) {
  try {
    localStorage.setItem(`${SETTINGS_STORAGE_KEY}_${connectorId}`, JSON.stringify(settings));
  } catch {}
}

function ToggleSwitch({
  checked,
  onChange,
  id,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  id: string;
}) {
  return (
    <motion.button
      role="switch"
      aria-checked={checked}
      id={id}
      onClick={() => onChange(!checked)}
      whileTap={{ scale: 0.9 }}
      style={{
        width: 42,
        height: 24,
        borderRadius: 12,
        padding: 0,
        border: "none",
        cursor: "pointer",
        position: "relative",
        background: checked ? "var(--accent-primary)" : "var(--border-strong)",
        transition: `background ${dur.fast}s ease`,
        flexShrink: 0,
        boxShadow: checked ? "0 0 0 3px var(--accent-muted)" : "none",
      }}
    >
      <motion.div
        animate={{ x: checked ? 20 : 2 }}
        transition={{ duration: dur.fast, ease: "easeOut" }}
        style={{
          width: 20,
          height: 20,
          borderRadius: "50%",
          background: "var(--surface)",
          boxShadow: "var(--shadow-sm)",
          position: "absolute",
          top: 2,
        }}
      />
    </motion.button>
  );
}

export default function ConnectorSettings({ connector }: ConnectorSettingsProps) {
  const [toggles, setToggles] = useState<Record<string, boolean>>(() => loadSettings(connector.id));
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setToggles(loadSettings(connector.id));
  }, [connector.id]);

  function handleToggle(key: string) {
    setToggles((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      saveSettings(connector.id, next);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      return next;
    });
  }

  const groups = Array.from(new Set(TOGGLES.map((t) => t.group)));

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
          <Settings size={16} />
        </div>
        <div>
          <p style={{ fontSize: "var(--font-size-sm)", fontWeight: 700, color: "var(--text-primary)", margin: 0, letterSpacing: "-0.01em" }}>
            {connector.name} Settings
          </p>
          <p style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", margin: 0 }}>
            Configure connector behavior and access controls
          </p>
        </div>
      </div>

      {groups.map((group) => {
        const groupToggles = TOGGLES.filter((t) => t.group === group);
        return (
          <div key={group}>
            <p style={{
              fontSize: "var(--font-size-label)", fontWeight: 700, color: "var(--text-primary)",
              margin: "0 0 var(--space-2)", letterSpacing: "0.04em", textTransform: "uppercase",
            }}>
              {group}
            </p>
            <div style={{ borderRadius: "var(--radius-sm)", border: "1px solid var(--border)", overflow: "hidden" }}>
              {groupToggles.map((toggle, i) => (
                <div
                  key={toggle.key}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "14px 16px",
                    background: i % 2 === 0 ? "var(--surface)" : "var(--surface-raised)",
                    borderBottom: i < groupToggles.length - 1 ? "1px solid var(--border)" : "none",
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0, paddingRight: 16 }}>
                    <label
                      htmlFor={`setting-${connector.id}-${toggle.key}`}
                      style={{
                        fontSize: "var(--font-size-sm)", fontWeight: 600, color: "var(--text-primary)",
                        display: "block", marginBottom: 2, cursor: "pointer",
                      }}
                    >
                      {toggle.label}
                    </label>
                    <p style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", margin: 0, lineHeight: 1.45 }}>
                      {toggle.description}
                    </p>
                  </div>
                  <ToggleSwitch
                    checked={toggles[toggle.key]}
                    onChange={() => handleToggle(toggle.key)}
                    id={`setting-${connector.id}-${toggle.key}`}
                  />
                </div>
              ))}
            </div>
          </div>
        );
      })}

      {saved && (
        <div style={{
          display: "flex", alignItems: "center", gap: 6,
          padding: "8px 14px", borderRadius: "var(--radius-sm)",
          background: "var(--success-muted)", border: "1px solid var(--success-border)",
          fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--success)",
        }}>
          <Check size={13} />
          Settings saved
        </div>
      )}
    </div>
  );
}
