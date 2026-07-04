"use client"

import { useEffect, useState, useCallback, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Keyboard, Command, ArrowUp, ArrowDown, ArrowLeft, ArrowRight, CornerDownLeft, X } from "lucide-react"

export type ShortcutMap = Record<string, (e: KeyboardEvent) => void>

export function useKeyboardShortcuts(shortcuts: ShortcutMap, enabled = true) {
  const shortcutRef = useRef(shortcuts)
  shortcutRef.current = shortcuts

  useEffect(() => {
    if (!enabled) return

    const handler = (e: KeyboardEvent) => {
      const key = serializeKey(e)
      const handlerFn = shortcutRef.current[key]
      if (handlerFn) {
        e.preventDefault()
        e.stopPropagation()
        handlerFn(e)
      }
    }

    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [enabled])
}

function serializeKey(e: KeyboardEvent): string {
  const parts: string[] = []
  if (e.ctrlKey || e.metaKey) parts.push("mod")
  if (e.shiftKey) parts.push("shift")
  if (e.altKey) parts.push("alt")
  const key = e.key === " " ? "space" : e.key.toLowerCase()
  if (!["control", "meta", "shift", "alt"].includes(key)) {
    parts.push(key)
  }
  return parts.join("+")
}

interface ShortcutGroup {
  label: string
  shortcuts: { keys: string; description: string }[]
}

const shortcutGroups: ShortcutGroup[] = [
  {
    label: "Navigation",
    shortcuts: [
      { keys: "G D", description: "Dashboard" },
      { keys: "G R", description: "Runtime" },
      { keys: "G A", description: "Agents" },
      { keys: "G M", description: "Missions" },
      { keys: "G V", description: "Voice" },
      { keys: "G B", description: "Browser" },
      { keys: "G P", description: "Replay" },
      { keys: "G O", description: "Operations Center" },
    ],
  },
  {
    label: "Search",
    shortcuts: [
      { keys: "Ctrl+K", description: "Command Palette" },
      { keys: "Ctrl+Shift+F", description: "Search" },
    ],
  },
  {
    label: "Mission",
    shortcuts: [
      { keys: "Ctrl+Enter", description: "Execute" },
      { keys: "Escape", description: "Cancel" },
    ],
  },
  {
    label: "Replay",
    shortcuts: [
      { keys: "Space", description: "Play / Pause" },
      { keys: "→", description: "Step Forward" },
      { keys: "←", description: "Step Back" },
    ],
  },
  {
    label: "General",
    shortcuts: [
      { keys: "?", description: "Show Shortcuts" },
      { keys: "Ctrl+,", description: "Settings" },
    ],
  },
]

function formatKeysDisplay(keys: string): string[] {
  const replacements: Record<string, string> = {
    "Ctrl+K": "⌘K",
    "Ctrl+Shift+F": "⌘⇧F",
    "Ctrl+Enter": "⌘↵",
    "Ctrl+,": "⌘,",
    Escape: "Esc",
    Space: "␣",
    "→": "→",
    "←": "←",
  }
  if (replacements[keys]) {
    const val = replacements[keys]
    if (keys.includes("Ctrl")) {
      return val.split("").map((c) => (c === "⌘" ? "⌘" : c === "⇧" ? "⇧" : c === "F" ? "F" : c === "K" ? "K" : c === "↵" ? "↵" : c === "," ? "," : c))
    }
    return [val]
  }

  return keys
    .split(" ")
    .map((k) => replacements[k] || k)
}

const overlayVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
}

const modalVariants = {
  hidden: { opacity: 0, scale: 0.95, y: -20 },
  visible: { opacity: 1, scale: 1, y: 0, transition: { type: "spring" as const, damping: 25, stiffness: 300 } },
}

export default function ShortcutsModal({ onClose }: { onClose?: () => void }) {
  const [open, setOpen] = useState(false)

  useKeyboardShortcuts(
    {
      "?": () => setOpen((prev) => !prev),
      escape: () => setOpen(false),
    },
    true
  )

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [open])

  const handleBackdropClick = useCallback((e: React.MouseEvent) => {
    if (e.target === e.currentTarget) setOpen(false)
  }, [])

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm"
          variants={overlayVariants}
          initial="hidden"
          animate="visible"
          exit="hidden"
          onClick={handleBackdropClick}
        >
          <motion.div
            className="w-full max-w-lg overflow-hidden rounded-[18px] border border-[#E8EDF3] bg-white shadow-xl"
            variants={modalVariants}
            initial="hidden"
            animate="visible"
            exit="hidden"
          >
            <div className="flex items-center justify-between border-b border-[#E8EDF3] px-5 py-4">
              <div className="flex items-center gap-2">
                <Keyboard size={18} className="text-gray-500" />
                <h2 className="text-[15px] font-semibold text-gray-900">Keyboard Shortcuts</h2>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="flex h-7 w-7 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
              >
                <X size={15} />
              </button>
            </div>

            <div className="max-h-[460px] overflow-y-auto px-5 py-4">
              {shortcutGroups.map((group) => (
                <div key={group.label} className="mb-5 last:mb-0">
                  <div className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-gray-400">
                    {group.label}
                  </div>
                  <div className="space-y-1">
                    {group.shortcuts.map((shortcut) => {
                      const keys = shortcut.keys.startsWith("Ctrl")
                        ? shortcut.keys.replace(/^Ctrl/, "⌘").split("+")
                        : formatKeysDisplay(shortcut.keys)
                      return (
                        <div
                          key={shortcut.keys + shortcut.description}
                          className="flex items-center justify-between rounded-lg px-3 py-2 transition-colors hover:bg-gray-50"
                        >
                          <span className="text-[13px] text-gray-700">{shortcut.description}</span>
                          <div className="flex items-center gap-1">
                            {(Array.isArray(keys) ? keys : [keys]).map((key, i) => (
                              <span key={i}>
                                {i > 0 && <span className="mx-0.5 text-[10px] text-gray-300">+</span>}
                                <kbd className="inline-flex min-w-[24px] items-center justify-center rounded-md border border-[#E8EDF3] bg-gray-50 px-1.5 py-0.5 text-[11px] font-medium text-gray-600 shadow-sm">
                                  {key === "⌘" ? (
                                    <Command size={11} />
                                  ) : key === "→" ? (
                                    <ArrowRight size={11} />
                                  ) : key === "←" ? (
                                    <ArrowLeft size={11} />
                                  ) : key === "↑" ? (
                                    <ArrowUp size={11} />
                                  ) : key === "↓" ? (
                                    <ArrowDown size={11} />
                                  ) : key === "↵" ? (
                                    <CornerDownLeft size={11} />
                                  ) : (
                                    key
                                  )}
                                </kbd>
                              </span>
                            ))}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>

            <div className="border-t border-[#E8EDF3] px-5 py-3 text-center text-[11px] text-gray-400">
              Press <kbd className="rounded border border-[#E8EDF3] px-1.5 py-0.5 text-[10px] font-medium text-gray-500">?</kbd> to toggle this panel
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}