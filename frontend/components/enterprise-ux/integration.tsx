"use client"

import { useEffect, useCallback, type ReactNode } from "react"
import { useRouter, usePathname } from "next/navigation"
import dynamic from "next/dynamic"
import { useUxStore } from "@/store/uxStore"
import { ErrorBoundary } from "./product-polish"

const CommandCenter = dynamic(() => import("./command-center"), { ssr: false })
const NotificationPanel = dynamic(() => import("./notification-center"), { ssr: false })
const ShortcutsModal = dynamic(() => import("./keyboard-shortcuts"), { ssr: false })

export function GlobalCommandCenter() {
  const open = useUxStore((s) => s.commandCenterOpen)
  const setOpen = useUxStore((s) => s.setCommandCenterOpen)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault()
        setOpen(!open)
      }
      if (e.key === "Escape" && open) {
        setOpen(false)
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [open, setOpen])

  if (!open) return null
  return <CommandCenter onClose={() => setOpen(false)} />
}

export function GlobalNotificationCenter() {
  const open = useUxStore((s) => s.notificationCenterOpen)
  const setOpen = useUxStore((s) => s.setNotificationCenterOpen)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) {
        setOpen(false)
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [open, setOpen])

  if (!open) return null
  return <NotificationPanel onClose={() => setOpen(false)} />
}

export function GlobalShortcutsModal() {
  const open = useUxStore((s) => s.shortcutsModalOpen)
  const setOpen = useUxStore((s) => s.setShortcutsModalOpen)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "?" && !(e.ctrlKey || e.metaKey)) {
        e.preventDefault()
        setOpen(!open)
      }
      if (e.key === "Escape" && open) {
        setOpen(false)
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [open, setOpen])

  return <ShortcutsModal onClose={() => setOpen(false)} />
}

export function GlobalKeyboardShortcuts() {
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (!e.ctrlKey && !e.metaKey) return

      const key = e.key.toLowerCase()
      const setOpen = useUxStore.getState().setCommandCenterOpen

      switch (key) {
        case "k":
          e.preventDefault()
          setOpen(true)
          break
        case ",":
          e.preventDefault()
          useUxStore.getState().setPreferencesOpen(true)
          break
        case "enter":
          e.preventDefault()
          const executeBtn = document.querySelector('[data-command="execute-mission"]') as HTMLButtonElement
          executeBtn?.click()
          break
      }
    }

    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [router, pathname])

  return null
}

export function GlobalAccessibilityProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    const handleKeyDown = () => {
      document.body.classList.add("keyboard-mode")
      document.body.classList.remove("mouse-mode")
    }
    const handleMouseDown = () => {
      document.body.classList.add("mouse-mode")
      document.body.classList.remove("keyboard-mode")
    }

    window.addEventListener("keydown", handleKeyDown)
    window.addEventListener("mousedown", handleMouseDown)

    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)")
    const handleMotion = (e: MediaQueryListEvent) => {
      useUxStore.getState().setReducedMotion(e.matches)
    }
    mediaQuery.addEventListener("change", handleMotion)
    useUxStore.getState().setReducedMotion(mediaQuery.matches)

    return () => {
      window.removeEventListener("keydown", handleKeyDown)
      window.removeEventListener("mousedown", handleMouseDown)
      mediaQuery.removeEventListener("change", handleMotion)
    }
  }, [])

  return (
    <>
      <SkipLink />
      <AriaLiveRegion />
      {children}
    </>
  )
}

function SkipLink() {
  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[100] focus:px-4 focus:py-2 focus:rounded-[10px] focus:bg-[#38B88A] focus:text-white focus:text-[0.82rem] focus:font-semibold focus:shadow-lg focus:outline-none"
    >
      Skip to main content
    </a>
  )
}

function AriaLiveRegion() {
  return (
    <div aria-live="polite" role="status" className="sr-only" id="cortex-aria-live" />
  )
}

export function EnterpriseUXSync() {
  const accentColor = useUxStore((s) => s.accentColor)
  const themePreset = useUxStore((s) => s.themePreset)
  const fontSize = useUxStore((s) => s.fontSize)
  const reducedMotion = useUxStore((s) => s.reducedMotion)

  useEffect(() => {
    const root = document.documentElement
    root.style.setProperty("--accent", accentColor)
    root.style.setProperty("--accent-hover", accentColor + "dd")
    root.style.setProperty("--accent-light", accentColor + "15")
    root.style.setProperty("--accent-border", accentColor + "30")

    switch (fontSize) {
      case "small": root.style.fontSize = "14px"; break
      case "medium": root.style.fontSize = "16px"; break
      case "large": root.style.fontSize = "18px"; break
    }

    document.body.classList.toggle("reduced-motion", reducedMotion)
  }, [accentColor, themePreset, fontSize, reducedMotion])

  return null
}

export function EnterpriseUXProvider({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary>
      <GlobalAccessibilityProvider>
        <EnterpriseUXSync />
        <GlobalCommandCenter />
        <GlobalNotificationCenter />
        <GlobalShortcutsModal />
        <GlobalKeyboardShortcuts />
        {children}
      </GlobalAccessibilityProvider>
    </ErrorBoundary>
  )
}