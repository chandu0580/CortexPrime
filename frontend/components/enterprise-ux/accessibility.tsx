"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Keyboard } from "lucide-react"

import { cn } from "@/utils/cn"

// ─── Types ─────────────────────────────────────────────────────────────────

interface AccessibilityContextValue {
  isReducedMotion: boolean
  isKeyboardMode: boolean
  announce: (message: string) => void
  focusTrapRef: RefObject<HTMLDivElement | null>
}

// ─── Context ───────────────────────────────────────────────────────────────

const AccessibilityContext = createContext<AccessibilityContextValue>({
  isReducedMotion: false,
  isKeyboardMode: false,
  announce: () => {},
  focusTrapRef: { current: null },
})

// ─── AriaProvider ──────────────────────────────────────────────────────────

export function AriaProvider({ children }: { children: ReactNode }) {
  const [isReducedMotion, setIsReducedMotion] = useState(false)
  const [isKeyboardMode, setIsKeyboardMode] = useState(false)
  const [showKeyboardHint, setShowKeyboardHint] = useState(false)
  const liveRegionRef = useRef<HTMLDivElement>(null)
  const focusTrapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)")
    setIsReducedMotion(mq.matches)
    const handler = (e: MediaQueryListEvent) => setIsReducedMotion(e.matches)
    mq.addEventListener("change", handler)
    return () => mq.removeEventListener("change", handler)
  }, [])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Tab") {
        if (!isKeyboardMode) {
          setIsKeyboardMode(true)
          setShowKeyboardHint(true)
          document.body.classList.remove("mouse-mode")
          document.body.classList.add("keyboard-mode")
        }
      }
    }

    const handleMouseDown = () => {
      if (isKeyboardMode) {
        setIsKeyboardMode(false)
        document.body.classList.remove("keyboard-mode")
        document.body.classList.add("mouse-mode")
      }
    }

    document.addEventListener("keydown", handleKeyDown)
    document.addEventListener("mousedown", handleMouseDown)
    return () => {
      document.removeEventListener("keydown", handleKeyDown)
      document.removeEventListener("mousedown", handleMouseDown)
    }
  }, [isKeyboardMode])

  const announce = useCallback((message: string) => {
    if (liveRegionRef.current) {
      liveRegionRef.current.textContent = ""
      requestAnimationFrame(() => {
        if (liveRegionRef.current) {
          liveRegionRef.current.textContent = message
        }
      })
    }
  }, [])

  const value = useMemo<AccessibilityContextValue>(
    () => ({ isReducedMotion, isKeyboardMode, announce, focusTrapRef }),
    [isReducedMotion, isKeyboardMode, announce],
  )

  return (
    <AccessibilityContext.Provider value={value}>
      <div
        ref={liveRegionRef}
        aria-live="polite"
        role="status"
        className="sr-only"
      />
      {children}
      <AnimatePresence>
        {showKeyboardHint && isKeyboardMode && (
          <KeyboardIndicator onDismiss={() => setShowKeyboardHint(false)} />
        )}
      </AnimatePresence>
    </AccessibilityContext.Provider>
  )
}

// ─── Hook ──────────────────────────────────────────────────────────────────

export function useAccessibility(): AccessibilityContextValue {
  return useContext(AccessibilityContext)
}

// ─── AriaLiveRegion ────────────────────────────────────────────────────────

export function AriaLiveRegion({
  message,
  role = "status",
  "aria-live": ariaLive = "polite",
}: {
  message: string
  role?: "status" | "alert" | "log"
  "aria-live"?: "polite" | "assertive"
}) {
  return (
    <span
      role={role}
      aria-live={ariaLive}
      aria-atomic="true"
      className="sr-only"
    >
      {message}
    </span>
  )
}

// ─── FocusTrap ─────────────────────────────────────────────────────────────

export function FocusTrap({
  children,
  active = true,
  className,
}: {
  children: ReactNode
  active?: boolean
  className?: string
}) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!active || !containerRef.current) return

    const container = containerRef.current

    const focusableSelector =
      'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

    const getFocusableElements = () =>
      Array.from(
        container.querySelectorAll<HTMLElement>(focusableSelector),
      ).filter((el) => {
        const style = window.getComputedStyle(el)
        return style.display !== "none" && style.visibility !== "hidden"
      })

    const focusFirst = () => {
      const elements = getFocusableElements()
      if (elements.length > 0) {
        elements[0].focus()
      }
    }

    focusFirst()

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return

      const elements = getFocusableElements()
      if (elements.length === 0) {
        e.preventDefault()
        return
      }

      const first = elements[0]
      const last = elements[elements.length - 1]

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault()
          last.focus()
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }

    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [active])

  return (
    <div ref={containerRef} className={className}>
      {children}
    </div>
  )
}

// ─── SkipLink ──────────────────────────────────────────────────────────────

export function SkipLink({
  href = "#main-content",
  label = "Skip to main content",
  className,
}: {
  href?: string
  label?: string
  className?: string
}) {
  return (
    <a
      href={href}
      className={cn(
        "sr-only left-4 top-4 z-[9999] rounded-[12px] border border-[#E8EDF3] bg-white px-4 py-2 text-sm font-semibold text-[#111827] shadow-[0_4px_12px_rgba(148,163,184,0.12)] focus:not-sr-only focus:absolute focus:outline-none focus:ring-2 focus:ring-[#38B88A]",
        className,
      )}
    >
      {label}
    </a>
  )
}

// ─── KeyboardIndicator ─────────────────────────────────────────────────────

function KeyboardIndicator({ onDismiss }: { onDismiss: () => void }) {
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false)
      setTimeout(onDismiss, 300)
    }, 4000)
    return () => clearTimeout(timer)
  }, [onDismiss])

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={visible ? { opacity: 1, y: 0 } : { opacity: 0, y: 10 }}
      exit={{ opacity: 0, y: 10 }}
      transition={{ duration: 0.2 }}
      className="fixed bottom-6 left-1/2 z-[9999] -translate-x-1/2"
    >
      <div className="flex items-center gap-2 rounded-[14px] border border-[#E8EDF3] bg-white px-4 py-2.5 shadow-[0_4px_16px_rgba(148,163,184,0.15)]">
        <Keyboard className="h-4 w-4 text-[#6B7280]" />
        <span className="text-xs font-medium text-[#374151]">
          Tab to navigate
        </span>
        <button
          onClick={() => {
            setVisible(false)
            setTimeout(onDismiss, 300)
          }}
          className="ml-2 flex h-5 w-5 items-center justify-center rounded-full text-[9px] font-bold text-[#9CA3AF] transition-colors hover:bg-[#F3F4F6] hover:text-[#6B7280]"
          aria-label="Dismiss keyboard hint"
        >
          ✕
        </button>
      </div>
    </motion.div>
  )
}