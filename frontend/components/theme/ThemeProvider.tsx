"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export type Theme = "cortex-dark" | "cortex-light";

interface ThemeContextValue {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggle: () => void;
  isDark: boolean;
}

// ─────────────────────────────────────────────────────────────────────────────
// Context
// ─────────────────────────────────────────────────────────────────────────────

const ThemeContext = createContext<ThemeContextValue>({
  theme:    "cortex-light",
  setTheme: () => {},
  toggle:   () => {},
  isDark:   false,
});

const STORAGE_KEY = "cortex-theme";

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function resolveInitialTheme(): Theme {
  if (typeof window === "undefined") return "cortex-light";
  try {
    const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
    if (stored === "cortex-dark" || stored === "cortex-light") return stored;
    return "cortex-light";
  } catch {
    return "cortex-light";
  }
}

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  // Remove both, then set the active one
  root.classList.remove("cortex-dark", "cortex-light");
  root.classList.add(theme);
  root.setAttribute("data-theme", theme);
}

// ─────────────────────────────────────────────────────────────────────────────
// Provider
// ─────────────────────────────────────────────────────────────────────────────

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("cortex-light");
  const [mounted, setMounted] = useState(false);

  // Resolve + apply on mount (client only)
  useEffect(() => {
    const initial = resolveInitialTheme();
    setThemeState(initial);
    applyTheme(initial);
    setMounted(true);
  }, []);

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
    applyTheme(t);
    try { localStorage.setItem(STORAGE_KEY, t); } catch {}
  }, []);

  const toggle = useCallback(() => {
    setTheme(theme === "cortex-dark" ? "cortex-light" : "cortex-dark");
  }, [theme, setTheme]);

  // Prevent hydration flash — render nothing until mounted
  if (!mounted) return null;

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggle, isDark: theme === "cortex-dark" }}>
      {children}
    </ThemeContext.Provider>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Hook
// ─────────────────────────────────────────────────────────────────────────────

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}
