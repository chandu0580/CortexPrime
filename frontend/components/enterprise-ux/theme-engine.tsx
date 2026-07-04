"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Sun,
  Moon,
  Palette,
  Contrast,
  Type,
  Move,
  Check,
  Monitor,
} from "lucide-react"

import { ease } from "@/lib/motion-tokens"
import { cn } from "@/utils/cn"
import { useTheme } from "@/components/theme/ThemeProvider"

// ─── Types ─────────────────────────────────────────────────────────────────

export type AccentColor = string
export type ContrastLevel = "normal" | "high" | "low"
export type ThemePreset = "cortex" | "minimal" | "ocean" | "sunset" | "forest"
export type FontSize = "small" | "medium" | "large"

interface ExtendedThemeContextValue {
  mode: "dark" | "light"
  accentColor: AccentColor
  setAccentColor: (color: string) => void
  contrast: ContrastLevel
  setContrast: (c: ContrastLevel) => void
  themePreset: ThemePreset
  setThemePreset: (p: ThemePreset) => void
  reducedMotion: boolean
  setReducedMotion: (b: boolean) => void
  fontSize: FontSize
  setFontSize: (s: FontSize) => void
}

interface ExtendedThemeState {
  accentColor: AccentColor
  contrast: ContrastLevel
  themePreset: ThemePreset
  reducedMotion: boolean
  fontSize: FontSize
}

// ─── Presets ───────────────────────────────────────────────────────────────

const PRESETS: Record<ThemePreset, { accent: string; bg: string; darkBg: string }> = {
  cortex: { accent: "#38B88A", bg: "#FFFFFF", darkBg: "#0F172A" },
  minimal: { accent: "#6B7280", bg: "#FFFFFF", darkBg: "#111827" },
  ocean: { accent: "#3B82F6", bg: "#F0F9FF", darkBg: "#0C1E3F" },
  sunset: { accent: "#F59E0B", bg: "#FFFBEB", darkBg: "#1C1504" },
  forest: { accent: "#059669", bg: "#ECFDF5", darkBg: "#022C22" },
}

const ACCENT_SWATCHES = [
  "#38B88A", "#6B7280", "#3B82F6", "#F59E0B",
  "#059669", "#EF4444", "#8B5CF6", "#EC4899",
]

const FONT_SIZE_MAP: Record<FontSize, string> = {
  small: "14px",
  medium: "16px",
  large: "18px",
}

// ─── Storage ───────────────────────────────────────────────────────────────

const STORAGE_KEY = "cortex-theme-extended"

function loadState(): ExtendedThemeState {
  if (typeof window === "undefined") {
    return { accentColor: "#38B88A", contrast: "normal", themePreset: "cortex", reducedMotion: false, fontSize: "medium" }
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      const mq = window.matchMedia("(prefers-reduced-motion: reduce)")
      return { accentColor: "#38B88A", contrast: "normal", themePreset: "cortex", reducedMotion: mq.matches, fontSize: "medium" }
    }
    return JSON.parse(raw) as ExtendedThemeState
  } catch {
    return { accentColor: "#38B88A", contrast: "normal", themePreset: "cortex", reducedMotion: false, fontSize: "medium" }
  }
}

function saveState(state: ExtendedThemeState): void {
  if (typeof window === "undefined") return
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {}
}

// ─── Context ───────────────────────────────────────────────────────────────

const ExtendedThemeContext = createContext<ExtendedThemeContextValue>({
  mode: "light",
  accentColor: "#38B88A",
  setAccentColor: () => {},
  contrast: "normal",
  setContrast: () => {},
  themePreset: "cortex",
  setThemePreset: () => {},
  reducedMotion: false,
  setReducedMotion: () => {},
  fontSize: "medium",
  setFontSize: () => {},
})

// ─── Provider ──────────────────────────────────────────────────────────────

export function ExtendedThemeProvider({ children }: { children: ReactNode }) {
  const { theme, isDark } = useTheme()
  const [state, setState] = useState<ExtendedThemeState>(loadState)

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)")
    const handler = () => {
      setState((prev) => ({ ...prev, reducedMotion: mq.matches }))
    }
    mq.addEventListener("change", handler)
    return () => mq.removeEventListener("change", handler)
  }, [])

  useEffect(() => {
    saveState(state)
  }, [state])

  const preset = PRESETS[state.themePreset]
  const bgColor = isDark ? preset.darkBg : preset.bg

  useEffect(() => {
    const root = document.documentElement
    root.style.setProperty("--accent", state.accentColor)
    root.style.setProperty("--accent-bg", bgColor)
    root.style.setProperty("--font-size-base", FONT_SIZE_MAP[state.fontSize])

    const contrastVal = state.contrast === "high" ? "1.2" : state.contrast === "low" ? "0.85" : "1"
    root.style.setProperty("--contrast", contrastVal)
    root.style.setProperty("--reduced-motion", state.reducedMotion ? "reduce" : "no-preference")
  }, [state, bgColor])

  const setAccentColor = useCallback((color: string) => {
    setState((prev) => ({ ...prev, accentColor: color }))
  }, [])

  const setContrast = useCallback((c: ContrastLevel) => {
    setState((prev) => ({ ...prev, contrast: c }))
  }, [])

  const setThemePreset = useCallback((p: ThemePreset) => {
    const preset = PRESETS[p]
    setState((prev) => ({ ...prev, themePreset: p, accentColor: preset.accent }))
  }, [])

  const setReducedMotion = useCallback((b: boolean) => {
    setState((prev) => ({ ...prev, reducedMotion: b }))
  }, [])

  const setFontSize = useCallback((s: FontSize) => {
    setState((prev) => ({ ...prev, fontSize: s }))
  }, [])

  const value = useMemo<ExtendedThemeContextValue>(
    () => ({
      mode: isDark ? "dark" : "light",
      accentColor: state.accentColor,
      setAccentColor,
      contrast: state.contrast,
      setContrast,
      themePreset: state.themePreset,
      setThemePreset,
      reducedMotion: state.reducedMotion,
      setReducedMotion,
      fontSize: state.fontSize,
      setFontSize,
    }),
    [isDark, state, setAccentColor, setContrast, setThemePreset, setReducedMotion, setFontSize],
  )

  return (
    <ExtendedThemeContext.Provider value={value}>
      {children}
    </ExtendedThemeContext.Provider>
  )
}

// ─── Hook ──────────────────────────────────────────────────────────────────

export function useExtendedTheme(): ExtendedThemeContextValue {
  return useContext(ExtendedThemeContext)
}

// ─── ThemeEnginePanel ──────────────────────────────────────────────────────

const PRESET_CARDS = [
  { id: "cortex" as ThemePreset, label: "Cortex", accent: "#38B88A", bg: "#FFFFFF" },
  { id: "minimal" as ThemePreset, label: "Minimal", accent: "#6B7280", bg: "#FFFFFF" },
  { id: "ocean" as ThemePreset, label: "Ocean", accent: "#3B82F6", bg: "#F0F9FF" },
  { id: "sunset" as ThemePreset, label: "Sunset", accent: "#F59E0B", bg: "#FFFBEB" },
  { id: "forest" as ThemePreset, label: "Forest", accent: "#059669", bg: "#ECFDF5" },
]

const CONTRAST_OPTIONS: ContrastLevel[] = ["normal", "high", "low"]
const FONT_OPTIONS: FontSize[] = ["small", "medium", "large"]

export function ThemeEnginePanel({ className }: { className?: string }) {
  const {
    mode,
    accentColor,
    setAccentColor,
    contrast,
    setContrast,
    themePreset,
    setThemePreset,
    reducedMotion,
    setReducedMotion,
    fontSize,
    setFontSize,
  } = useExtendedTheme()
  const { toggle } = useTheme()

  return (
    <div className={cn("rounded-[18px] border border-[#E8EDF3] bg-white shadow-[0_4px_12px_rgba(148,163,184,0.08)]", className)}>
      {/* Mode Toggle */}
      <div className="flex items-center justify-between border-b border-[#E8EDF3] px-5 py-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-[#111827]">
          <Palette className="h-4 w-4 text-[#38B88A]" />
          Theme Engine
        </div>
        <motion.button
          onClick={toggle}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className={cn(
            "flex items-center gap-2 rounded-[12px] border px-3.5 py-2 text-xs font-semibold transition-colors",
            mode === "dark"
              ? "border-[#374151] bg-[#1F2937] text-[#F9FAFB]"
              : "border-[#E8EDF3] bg-white text-[#374151]",
          )}
        >
          <AnimatePresence mode="wait" initial={false}>
            {mode === "dark" ? (
              <motion.span
                key="moon"
                initial={{ opacity: 0, rotate: -30 }}
                animate={{ opacity: 1, rotate: 0 }}
                exit={{ opacity: 0, rotate: 30 }}
                transition={{ duration: 0.15 }}
                className="flex items-center"
              >
                <Moon className="h-3.5 w-3.5" />
              </motion.span>
            ) : (
              <motion.span
                key="sun"
                initial={{ opacity: 0, rotate: 30 }}
                animate={{ opacity: 1, rotate: 0 }}
                exit={{ opacity: 0, rotate: -30 }}
                transition={{ duration: 0.15 }}
                className="flex items-center"
              >
                <Sun className="h-3.5 w-3.5" />
              </motion.span>
            )}
          </AnimatePresence>
          {mode === "dark" ? "Dark" : "Light"}
        </motion.button>
      </div>

      <div className="space-y-6 p-5">
        {/* Theme Preset */}
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-[#6B7280]">Theme Preset</p>
          <div className="grid grid-cols-5 gap-2">
            {PRESET_CARDS.map((presetItem) => (
              <motion.button
                key={presetItem.id}
                onClick={() => setThemePreset(presetItem.id)}
                whileHover={{ y: -2, scale: 1.02 }}
                whileTap={{ scale: 0.97 }}
                transition={{ duration: 0.2, ease: ease.out }}
                className={cn(
                  "flex flex-col items-center gap-1.5 rounded-[14px] border p-3 transition-colors",
                  themePreset === presetItem.id
                    ? "border-[#38B88A] bg-[#F0FDF4]"
                    : "border-[#E8EDF3] bg-white hover:border-[#D1D5DB]",
                )}
              >
                <div
                  className="h-6 w-6 rounded-full border border-[#E8EDF3]"
                  style={{ backgroundColor: presetItem.accent }}
                />
                <span className="text-[10px] font-medium text-[#374151]">{presetItem.label}</span>
              </motion.button>
            ))}
          </div>
        </div>

        {/* Accent Color */}
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-[#6B7280]">Accent Color</p>
          <div className="flex flex-wrap gap-2">
            {ACCENT_SWATCHES.map((swatch) => (
              <motion.button
                key={swatch}
                onClick={() => setAccentColor(swatch)}
                whileHover={{ scale: 1.15 }}
                whileTap={{ scale: 0.9 }}
                className={cn(
                  "relative flex h-7 w-7 items-center justify-center rounded-full border transition-colors",
                  accentColor === swatch ? "border-[#111827] ring-2 ring-[#38B88A]/30" : "border-[#E8EDF3]",
                )}
                style={{ backgroundColor: swatch }}
                aria-label={`Accent color ${swatch}`}
              >
                {accentColor === swatch && (
                  <Check className="h-3.5 w-3.5 text-white drop-shadow" strokeWidth={3} />
                )}
              </motion.button>
            ))}
          </div>
        </div>

        {/* Contrast */}
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-[#6B7280]">Contrast</p>
          <div className="flex gap-2">
            {CONTRAST_OPTIONS.map((opt) => (
              <motion.button
                key={opt}
                onClick={() => setContrast(opt)}
                whileTap={{ scale: 0.97 }}
                className={cn(
                  "flex items-center gap-1.5 rounded-[12px] border px-3.5 py-2 text-xs font-semibold transition-colors",
                  contrast === opt
                    ? "border-[#38B88A] bg-[#38B88A] text-white"
                    : "border-[#E8EDF3] bg-white text-[#374151] hover:border-[#D1D5DB]",
                )}
              >
                <Contrast className="h-3.5 w-3.5" />
                {opt.charAt(0).toUpperCase() + opt.slice(1)}
              </motion.button>
            ))}
          </div>
        </div>

        {/* Font Size */}
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-[#6B7280]">Font Size</p>
          <div className="flex gap-2">
            {FONT_OPTIONS.map((opt) => (
              <motion.button
                key={opt}
                onClick={() => setFontSize(opt)}
                whileTap={{ scale: 0.97 }}
                className={cn(
                  "flex items-center gap-1.5 rounded-[12px] border px-3.5 py-2 text-xs font-semibold transition-colors",
                  fontSize === opt
                    ? "border-[#38B88A] bg-[#38B88A] text-white"
                    : "border-[#E8EDF3] bg-white text-[#374151] hover:border-[#D1D5DB]",
                )}
              >
                <Type className="h-3.5 w-3.5" />
                {opt.charAt(0).toUpperCase() + opt.slice(1)}
              </motion.button>
            ))}
          </div>
        </div>

        {/* Reduced Motion */}
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-[#6B7280]">Motion</p>
          <motion.button
            onClick={() => setReducedMotion(!reducedMotion)}
            whileTap={{ scale: 0.97 }}
            className={cn(
              "flex items-center gap-2 rounded-[12px] border px-3.5 py-2 text-xs font-semibold transition-colors",
              reducedMotion
                ? "border-[#38B88A] bg-[#38B88A] text-white"
                : "border-[#E8EDF3] bg-white text-[#374151] hover:border-[#D1D5DB]",
            )}
          >
            <Monitor className="h-3.5 w-3.5" />
            {reducedMotion ? "Reduced motion ON" : "Reduced motion OFF"}
          </motion.button>
        </div>
      </div>
    </div>
  )
}