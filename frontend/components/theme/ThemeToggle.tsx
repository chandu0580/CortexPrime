"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "./ThemeProvider";

// ─────────────────────────────────────────────────────────────────────────────
// ThemeToggle — compact icon button used in Navbar + Sidebar
// ─────────────────────────────────────────────────────────────────────────────

interface ThemeToggleProps {
  /** compact = icon only; full = icon + label */
  variant?: "compact" | "full";
}

export default function ThemeToggle({ variant = "compact" }: ThemeToggleProps) {
  const { theme, toggle, isDark } = useTheme();

  return (
    <motion.button
      onClick={toggle}
      whileHover={{ scale: 1.08 }}
      whileTap={{ scale: 0.93 }}
      aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
      title={`Switch to ${isDark ? "light" : "dark"} mode`}
      style={{
        display:        "inline-flex",
        alignItems:     "center",
        gap:            6,
        padding:        variant === "full" ? "6px 12px" : "6px",
        borderRadius:   "var(--radius-md)",
        border:         "1px solid var(--border)",
        background:     "var(--surface-raised)",
        color:          "var(--text-secondary)",
        cursor:         "pointer",
        transition:     "all 0.2s ease",
        flexShrink:     0,
      }}
    >
      <AnimatePresence mode="wait" initial={false}>
        {isDark ? (
          <motion.span
            key="moon"
            initial={{ opacity: 0, rotate: -30 }}
            animate={{ opacity: 1, rotate: 0 }}
            exit={{ opacity: 0, rotate: 30 }}
            transition={{ duration: 0.15 }}
            style={{ display: "flex", alignItems: "center" }}
          >
            <Moon size={14} />
          </motion.span>
        ) : (
          <motion.span
            key="sun"
            initial={{ opacity: 0, rotate: 30 }}
            animate={{ opacity: 1, rotate: 0 }}
            exit={{ opacity: 0, rotate: -30 }}
            transition={{ duration: 0.15 }}
            style={{ display: "flex", alignItems: "center" }}
          >
            <Sun size={14} />
          </motion.span>
        )}
      </AnimatePresence>
      {variant === "full" && (
        <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, letterSpacing: "0.04em" }}>
          {isDark ? "Dark" : "Light"}
        </span>
      )}
    </motion.button>
  );
}
