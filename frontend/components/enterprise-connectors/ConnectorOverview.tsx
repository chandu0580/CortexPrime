"use client";

import { motion } from "framer-motion";
import { Plug, CheckCircle, ArrowRight, Zap } from "lucide-react";
import { ConnectorIcon, CONNECTOR_BRAND_COLORS } from "./ConnectorIcons";
import { dur, ease } from "@/lib/motion-tokens";
import type { Connector } from "./types";

interface ConnectorOverviewProps {
  connector: Connector;
  onConnect: () => void;
  onDisconnect?: () => void;
}

export default function ConnectorOverview({
  connector,
  onConnect,
  onDisconnect,
}: ConnectorOverviewProps) {
  const isConnected =
    connector.status === "connected" || connector.status === "healthy";
  const brand = CONNECTOR_BRAND_COLORS[connector.id];

  // ── Disconnected / empty state ─────────────────────────────────────────────
  if (!isConnected) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: dur.base, ease: ease.out }}
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          textAlign: "center",
          padding: "var(--space-8) var(--space-6)",
          gap: "var(--space-5)",
        }}
      >
        {/* Layered illustration */}
        <div style={{ position: "relative", marginBottom: 4 }}>
          {/* Outer ring */}
          <div
            style={{
              width: 100,
              height: 100,
              borderRadius: "50%",
              background: brand.bg,
              border: `2px solid ${brand.border}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              position: "relative",
            }}
          >
            {/* Middle ring */}
            <div
              style={{
                width: 70,
                height: 70,
                borderRadius: "50%",
                background: brand.bg,
                border: `1px solid ${brand.border}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <ConnectorIcon id={connector.id} size={32} />
            </div>
          </div>

          {/* Plug badge — bottom right corner */}
          <div
            style={{
              position: "absolute",
              bottom: 0,
              right: 0,
              width: 32,
              height: 32,
              borderRadius: "50%",
              background: "var(--surface)",
              border: "2px solid var(--border)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--text-muted)",
            }}
          >
            <Plug size={14} />
          </div>
        </div>

        {/* Name + description */}
        <div>
          <h3
            style={{
              fontSize: "var(--font-size-xl)",
              fontWeight: 700,
              color: "var(--text-primary)",
              margin: "0 0 6px",
              letterSpacing: "-0.02em",
            }}
          >
            Connect {connector.name}
          </h3>
          <p
            style={{
              fontSize: "var(--font-size-sm)",
              color: "var(--text-secondary)",
              margin: 0,
              maxWidth: 360,
              lineHeight: 1.65,
            }}
          >
            Connect this enterprise platform to allow CortexPrime AI Agents to
            securely perform enterprise operations across your organization.
          </p>
        </div>

        {/* Capabilities preview */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, justifyContent: "center", maxWidth: 320 }}>
          {connector.capabilities.map((cap) => (
            <span
              key={cap.label}
              style={{
                fontSize: "var(--font-size-xs)",
                fontWeight: 500,
                color: brand.text,
                background: brand.bg,
                border: `1px solid ${brand.border}`,
                borderRadius: "var(--radius-sm)",
                padding: "3px 10px",
              }}
            >
              {cap.label}
            </span>
          ))}
        </div>

        {/* CTA */}
        <motion.button
          whileHover={{ y: -2, scale: 1.02 }}
          whileTap={{ scale: 0.97 }}
          onClick={onConnect}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "12px 28px",
            borderRadius: "var(--radius-md)",
            border: "none",
            background: "var(--accent-primary)",
            color: "var(--text-inverse)",
            fontSize: "var(--font-size-md)",
            fontWeight: 700,
            cursor: "pointer",
            letterSpacing: "-0.01em",
            boxShadow: "var(--shadow-accent)",
          }}
          aria-label={`Connect ${connector.name}`}
        >
          <Plug size={17} />
          Connect {connector.name}
        </motion.button>

        <p
          style={{
            fontSize: "var(--font-size-xs)",
            color: "var(--text-muted)",
            margin: 0,
            display: "flex",
            alignItems: "center",
            gap: 5,
          }}
        >
          <span
            style={{
              width: 5,
              height: 5,
              borderRadius: "50%",
              background: "var(--success)",
              flexShrink: 0,
              display: "inline-block",
            }}
          />
          All credentials are encrypted at rest and in transit
        </p>
      </motion.div>
    );
  }

  // ── Connected state ────────────────────────────────────────────────────────
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: dur.base, ease: ease.out }}
      style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}
    >
      {/* Header: icon + name + check */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
        <div
          style={{
            width: 52,
            height: 52,
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
          <ConnectorIcon id={connector.id} size={26} />
        </div>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 3 }}>
            <h3
              style={{
                fontSize: "var(--font-size-xl)",
                fontWeight: 700,
                color: "var(--text-primary)",
                margin: 0,
                letterSpacing: "-0.02em",
              }}
            >
              {connector.name}
            </h3>
            <CheckCircle
              size={17}
              style={{ color: "var(--success)", flexShrink: 0 }}
            />
          </div>
          <p
            style={{
              fontSize: "var(--font-size-sm)",
              color: "var(--text-secondary)",
              margin: 0,
              lineHeight: 1.5,
            }}
          >
            {connector.description}
          </p>
        </div>
      </div>

      {/* Long description */}
      <p
        style={{
          fontSize: "var(--font-size-sm)",
          color: "var(--text-secondary)",
          margin: 0,
          lineHeight: 1.7,
          padding: "var(--space-4)",
          background: "var(--surface-raised)",
          borderRadius: "var(--radius-sm)",
          border: "1px solid var(--border)",
        }}
      >
        {connector.longDescription}
      </p>

      {/* Capabilities */}
      <div>
        <p
          style={{
            fontSize: "var(--font-size-label)",
            fontWeight: 700,
            color: "var(--text-primary)",
            margin: "0 0 var(--space-3)",
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          Capabilities
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {connector.capabilities.map((cap) => (
            <span
              key={cap.label}
              style={{
                fontSize: "var(--font-size-xs)",
                fontWeight: 600,
                color: brand.text,
                background: brand.bg,
                border: `1px solid ${brand.border}`,
                borderRadius: "var(--radius-sm)",
                padding: "4px 12px",
              }}
            >
              {cap.label}
            </span>
          ))}
        </div>
      </div>

      {/* Supported operations */}
      <div>
        <p
          style={{
            fontSize: "var(--font-size-label)",
            fontWeight: 700,
            color: "var(--text-primary)",
            margin: "0 0 var(--space-3)",
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          Supported Operations
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          {connector.operations.map((op) => (
            <div
              key={op}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-3)",
                padding: "10px var(--space-4)",
                borderRadius: "var(--radius-sm)",
                background: "var(--surface-raised)",
                border: "1px solid var(--border)",
              }}
            >
              <Zap
                size={13}
                style={{ color: brand.text, flexShrink: 0 }}
              />
              <span
                style={{
                  fontSize: "var(--font-size-sm)",
                  color: "var(--text-secondary)",
                  fontWeight: 500,
                }}
              >
                {op}
              </span>
              <ArrowRight
                size={12}
                style={{ color: "var(--text-muted)", marginLeft: "auto", flexShrink: 0 }}
              />
            </div>
          ))}
        </div>
      </div>

      {onDisconnect && (
        <div style={{ borderTop: "1px solid var(--border)", paddingTop: "var(--space-4)", marginTop: "var(--space-4)", display: "flex", justifyContent: "center" }}>
          <motion.button
            whileHover={{ y: -1 }}
            whileTap={{ scale: 0.98 }}
            onClick={onDisconnect}
            style={{
              width: "100%",
              padding: "10px var(--space-4)",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--danger-border)",
              background: "var(--danger-muted)",
              color: "var(--danger)",
              fontSize: "var(--font-size-xs)",
              fontWeight: 700,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              letterSpacing: "-0.005em",
            }}
          >
            <Plug size={12} style={{ transform: "rotate(45deg)", flexShrink: 0 }} />
            Disconnect Integration
          </motion.button>
        </div>
      )}
    </motion.div>
  );
}
