"use client";

import { motion } from "framer-motion";
import { ShieldCheck, Info } from "lucide-react";
import { dur, ease } from "@/lib/motion-tokens";
import type { Connector } from "./types";

interface ConnectorPermissionsProps {
  connector: Connector;
}

export default function ConnectorPermissions({
  connector,
}: ConnectorPermissionsProps) {
  if (connector.permissions.length === 0) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          padding: "48px 24px",
          textAlign: "center",
          gap: "var(--space-3)",
        }}
      >
        <ShieldCheck
          size={36}
          style={{ color: "var(--text-muted)", opacity: 0.35 }}
        />
        <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-muted)", margin: 0 }}>
          No permission data available.
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-2)",
          paddingBottom: "var(--space-4)",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: "var(--radius-sm)",
            background: "var(--accent-muted)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--accent-primary)",
          }}
        >
          <ShieldCheck size={16} />
        </div>
        <div>
          <p
            style={{
              fontSize: "var(--font-size-sm)",
              fontWeight: 700,
              color: "var(--text-primary)",
              margin: 0,
              letterSpacing: "-0.01em",
            }}
          >
            OAuth Scopes &amp; Permissions
          </p>
          <p
            style={{
              fontSize: "var(--font-size-xs)",
              color: "var(--text-muted)",
              margin: 0,
            }}
          >
            Required for {connector.name} integration
          </p>
        </div>
      </div>

      {/* Permission chips — flowing wrap layout */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
        {connector.permissions.map((perm, i) => (
          <motion.div
            key={perm.key}
            initial={{ opacity: 0, scale: 0.92 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: dur.fast, ease: ease.out, delay: i * 0.04 }}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 12px",
              borderRadius: "var(--radius-pill)",
              background: "var(--surface-raised)",
              border: "1px solid var(--border)",
              cursor: "default",
            }}
            title={perm.scope}
          >
            <ShieldCheck
              size={11}
              style={{ color: "var(--accent-primary)", flexShrink: 0 }}
            />
            <code
              style={{
                fontSize: "var(--font-size-xs)",
                fontWeight: 600,
                color: "var(--text-secondary)",
                letterSpacing: "-0.005em",
                fontFamily: '"JetBrains Mono", "SF Mono", "Fira Code", monospace',
              }}
            >
              {perm.label}
            </code>
          </motion.div>
        ))}
      </div>

      {/* Scope detail table */}
      <div>
        <p
          style={{
            fontSize: "var(--font-size-label)",
            fontWeight: 700,
            color: "var(--text-primary)",
            margin: "0 0 var(--space-2)",
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          Scope Details
        </p>
        <div
          style={{
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border)",
            overflow: "hidden",
          }}
        >
          {connector.permissions.map((perm, i) => (
            <div
              key={perm.key}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "var(--space-3)",
                padding: "10px 14px",
                background: i % 2 === 0 ? "var(--surface)" : "var(--surface-raised)",
                borderBottom:
                  i < connector.permissions.length - 1
                    ? "1px solid var(--border)"
                    : "none",
              }}
            >
              <code
                style={{
                  fontSize: "var(--font-size-xs)",
                  fontWeight: 700,
                  color: "var(--accent-primary)",
                  fontFamily: '"JetBrains Mono", "SF Mono", monospace',
                  flexShrink: 0,
                  minWidth: 100,
                  paddingTop: 1,
                }}
              >
                {perm.label}
              </code>
              <span
                style={{
                  fontSize: "var(--font-size-xs)",
                  color: "var(--text-secondary)",
                  lineHeight: 1.5,
                }}
              >
                {perm.scope}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Informational note */}
      <div
        style={{
          display: "flex",
          gap: "var(--space-2)",
          padding: "var(--space-3) var(--space-4)",
          background: "var(--accent-muted)",
          border: "1px solid var(--accent-border)",
          borderRadius: "var(--radius-sm)",
        }}
      >
        <Info size={14} style={{ color: "var(--accent-primary)", flexShrink: 0, marginTop: 1 }} />
        <p
          style={{
            fontSize: "var(--font-size-xs)",
            color: "var(--text-secondary)",
            margin: 0,
            lineHeight: 1.55,
          }}
        >
          These are the minimum permissions required by CortexPrime. No additional
          scopes are requested. All access follows the principle of least privilege.
        </p>
      </div>
    </div>
  );
}
