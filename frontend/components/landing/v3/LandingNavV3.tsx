"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import ThemeToggle from "@/components/theme/ThemeToggle";

const NAV_LINKS = [
  { label: "Architecture", href: "#architecture" },
  { label: "Capabilities", href: "#capabilities" },
  { label: "Demo",         href: "#demo" },
  { label: "Governance",   href: "#governance" },
  { label: "Memory",       href: "#memory" },
];

export default function LandingNavV3() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const h = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", h, { passive: true });
    return () => window.removeEventListener("scroll", h);
  }, []);

  return (
    <motion.nav
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5 }}
      style={{
        position:       "fixed",
        top:            0,
        left:           0,
        right:          0,
        zIndex:         100,
        padding:        "0 24px",
        height:         56,
        display:        "flex",
        alignItems:     "center",
        justifyContent: "space-between",
        background:     scrolled ? "var(--glass-bg)" : "transparent",
        backdropFilter: scrolled ? "blur(14px)" : "none",
        borderBottom:   scrolled ? "1px solid var(--border)" : "none",
        transition:     "background 0.3s, border-color 0.3s, backdrop-filter 0.3s",
      }}
    >
      {/* Brand */}
      <Link href="/" style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ width: 24, height: 24, borderRadius: "50%", background: "radial-gradient(circle at 35% 35%, #96cead, #82c0a4 60%, #0a6660)", boxShadow: "0 0 12px rgba(130,192,164,0.6)" }} />
        <span style={{ fontSize: "var(--font-size-md)", fontWeight: 800, color: "var(--text-primary)", letterSpacing: "-0.02em" }}>
          CortexPrime
        </span>
      </Link>

      {/* Desktop links */}
      <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
        {NAV_LINKS.map((l) => (
          <a key={l.label} href={l.href} style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--text-muted)", textDecoration: "none", letterSpacing: "0.02em", transition: "color 0.15s" }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = "var(--text-primary)"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = "var(--text-muted)"; }}
          >
            {l.label}
          </a>
        ))}
      </div>

      {/* CTAs + theme toggle */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <ThemeToggle variant="compact" />
        <Link href="/demo" style={{ padding: "6px 14px", borderRadius: "var(--radius-pill)", border: "1px solid var(--border)", color: "var(--text-secondary)", fontSize: "var(--font-size-xs)", fontWeight: 600, textDecoration: "none", transition: "border-color 0.15s, color 0.15s" }}
          onMouseEnter={(e) => { const el = e.currentTarget as HTMLElement; el.style.borderColor = "var(--accent-border)"; el.style.color = "var(--accent-primary)"; }}
          onMouseLeave={(e) => { const el = e.currentTarget as HTMLElement; el.style.borderColor = "var(--border)"; el.style.color = "var(--text-secondary)"; }}
        >
          Demo
        </Link>
        <Link href="/executive" style={{ padding: "6px 14px", borderRadius: "var(--radius-pill)", background: "linear-gradient(135deg, #82c0a4, #4a8c70)", color: "#fff", fontSize: "var(--font-size-xs)", fontWeight: 700, textDecoration: "none", boxShadow: "0 0 16px rgba(130,192,164,0.3)" }}>
          Launch →
        </Link>
      </div>
    </motion.nav>
  );
}
