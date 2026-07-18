"use client";

import { motion, AnimatePresence } from "framer-motion";
import ConnectorCard from "./ConnectorCard";
import type { Connector } from "./types";
import { dur, ease } from "@/lib/motion-tokens";

interface ConnectorGridProps {
  connectors: Connector[];
  onConnect: (id: string) => void;
  onViewDetails: (id: string) => void;
  viewMode?: "grid" | "list";
}

export default function ConnectorGrid({
  connectors,
  onConnect,
  onViewDetails,
  viewMode = "grid",
}: ConnectorGridProps) {
  if (connectors.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: dur.base, ease: ease.out }}
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "60px 20px",
          textAlign: "center",
          gap: "var(--space-4)",
        }}
      >
        <div
          style={{
            width: 58,
            height: 58,
            borderRadius: "var(--radius-xl)",
            background: "var(--surface-raised)",
            border: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--text-muted)",
          }}
        >
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>
        </div>
        <div>
          <p style={{ fontSize: "var(--font-size-md)", fontWeight: 700, color: "var(--text-primary)", margin: "0 0 5px", letterSpacing: "-0.01em" }}>
            No integrations found
          </p>
          <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-muted)", margin: 0, maxWidth: 280, lineHeight: 1.6 }}>
            Try adjusting your search or filter criteria.
          </p>
        </div>
      </motion.div>
    );
  }

  return (
    <div
      style={{
        display: "grid",
        gap: "var(--space-3)",
        gridTemplateColumns:
          viewMode === "list"
            ? "1fr"
            : "repeat(4, minmax(0, 1fr))",
      }}
    >
      <AnimatePresence mode="popLayout">
        {connectors.map((connector, i) => (
          <motion.div
            key={connector.id}
            layout
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: -4 }}
            transition={{ duration: dur.base, ease: ease.out, delay: i * 0.03 }}
          >
            <ConnectorCard
              connector={connector}
              onConnect={onConnect}
              onViewDetails={onViewDetails}
            />
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
