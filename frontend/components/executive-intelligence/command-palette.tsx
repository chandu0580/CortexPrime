"use client"

import { useEffect, useCallback, useState } from "react"
import { Search, Command, ArrowRight, Sparkles, Crosshair, FileText, Share2, MessageSquare, Settings, Shield, BarChart3, Terminal } from "lucide-react"
import { useRouter } from "next/navigation"
import { useIntelligenceStore } from "@/store/intelligenceStore"
import { cn } from "@/utils/cn"

const ACTIONS = [
  { id: "new-mission", icon: Crosshair, label: "Start New Mission", shortcut: "M", href: "/executive-platform/mission-control" },
  { id: "executive-chat", icon: MessageSquare, label: "Open Executive Chat", shortcut: "C", href: "/executive-platform/chat" },
  { id: "briefing", icon: FileText, label: "View Daily Briefing", shortcut: "B", href: "/executive-platform/intelligence" },
  { id: "knowledge", icon: Share2, label: "Search Knowledge Graph", shortcut: "K", href: "/executive-platform/knowledge-graph" },
  { id: "analytics", icon: BarChart3, label: "Open Analytics", shortcut: "A", href: "/executive-platform/analytics" },
  { id: "approvals", icon: Shield, label: "Review Approvals", shortcut: "P", href: "/executive-platform/approvals" },
  { id: "settings", icon: Settings, label: "Settings", shortcut: "S", href: "/executive-platform/settings" },
]

const SEARCH_CATEGORIES = [
  { id: "missions", label: "Missions", icon: Crosshair },
  { id: "memory", label: "Memory", icon: FileText },
  { id: "knowledge", label: "Knowledge", icon: Share2 },
  { id: "connectors", label: "Connectors", icon: Terminal },
  { id: "approvals", label: "Approvals", icon: Shield },
]

export function GlobalCommandPalette() {
  const { commandPaletteOpen, setCommandPalette } = useIntelligenceStore()
  const [query, setQuery] = useState("")
  const [selectedIndex, setSelectedIndex] = useState(0)
  const router = useRouter()

  const filtered = ACTIONS.filter((a) => a.label.toLowerCase().includes(query.toLowerCase()))

  const execute = useCallback((action: typeof ACTIONS[0]) => {
    setCommandPalette(false)
    setQuery("")
    router.push(action.href)
  }, [router, setCommandPalette])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        setCommandPalette(!commandPaletteOpen)
      }
      if (commandPaletteOpen && e.key === "Escape") {
        setCommandPalette(false)
        setQuery("")
      }
      if (commandPaletteOpen && e.key === "ArrowDown") {
        e.preventDefault()
        setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1))
      }
      if (commandPaletteOpen && e.key === "ArrowUp") {
        e.preventDefault()
        setSelectedIndex((i) => Math.max(i - 1, 0))
      }
      if (commandPaletteOpen && e.key === "Enter" && filtered[selectedIndex]) {
        e.preventDefault()
        execute(filtered[selectedIndex])
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [commandPaletteOpen, setCommandPalette, filtered, selectedIndex, execute])

  if (!commandPaletteOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]" onClick={() => setCommandPalette(false)}>
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="relative w-full max-w-lg border border-white/10 rounded-xl bg-[#0d0d14] shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 px-4 py-3 border-b border-white/5">
          <Command className="w-4 h-4 text-white/30" />
          <input
            autoFocus
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSelectedIndex(0) }}
            placeholder="Type a command or search..."
            className="flex-1 bg-transparent border-none outline-none text-sm text-white/80 placeholder:text-white/20"
          />
          <kbd className="text-[10px] text-white/20 border border-white/10 rounded px-1.5 py-0.5">ESC</kbd>
        </div>
        <div className="p-2 max-h-72 overflow-y-auto">
          {filtered.length === 0 ? (
            <div className="px-3 py-6 text-center text-sm text-white/30">No matching commands</div>
          ) : (
            filtered.map((action, i) => (
              <button
                key={action.id}
                onClick={() => execute(action)}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all",
                  i === selectedIndex ? "bg-emerald-500/10 text-emerald-300" : "text-white/60 hover:bg-white/5"
                )}
              >
                <action.icon className="w-4 h-4" />
                <span className="flex-1 text-left">{action.label}</span>
                <kbd className="text-[10px] text-white/20 border border-white/10 rounded px-1.5 py-0.5">{action.shortcut}</kbd>
              </button>
            ))
          )}
        </div>
        {!query && (
          <div className="px-4 py-2 border-t border-white/5 flex items-center gap-3 text-[10px] text-white/20">
            <span>↑↓ Navigate</span>
            <span>↵ Open</span>
            <span>⌘K Toggle</span>
          </div>
        )}
      </div>
    </div>
  )
}

export function GlobalSearch() {
  const { globalSearchOpen, setGlobalSearch } = useIntelligenceStore()
  const [query, setQuery] = useState("")
  const [category, setCategory] = useState("all")

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === "f") {
        e.preventDefault()
        setGlobalSearch(!globalSearchOpen)
      }
      if (globalSearchOpen && e.key === "Escape") {
        setGlobalSearch(false)
        setQuery("")
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [globalSearchOpen, setGlobalSearch])

  if (!globalSearchOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]" onClick={() => setGlobalSearch(false)}>
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="relative w-full max-w-2xl border border-white/10 rounded-xl bg-[#0d0d14] shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 px-4 py-3 border-b border-white/5">
          <Search className="w-4 h-4 text-white/30" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search missions, memory, knowledge, connectors, approvals..."
            className="flex-1 bg-transparent border-none outline-none text-sm text-white/80 placeholder:text-white/20"
          />
        </div>
        <div className="flex gap-1 px-3 pt-2">
          <button onClick={() => setCategory("all")} className={`px-2.5 py-1 rounded-md text-[11px] transition-all ${category === "all" ? "bg-white/10 text-white" : "text-white/30 hover:text-white/60"}`}>All</button>
          {SEARCH_CATEGORIES.map((c) => (
            <button key={c.id} onClick={() => setCategory(c.id)} className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] transition-all ${category === c.id ? "bg-white/10 text-white" : "text-white/30 hover:text-white/60"}`}>
              <c.icon className="w-3 h-3" />{c.label}
            </button>
          ))}
        </div>
        <div className="p-3 min-h-[120px]">
          {query.length < 2 ? (
            <div className="flex items-center justify-center h-20 text-sm text-white/20">Type at least 2 characters to search</div>
          ) : (
            <div className="flex items-center justify-center h-20 text-sm text-white/30">
              <Search className="w-4 h-4 mr-2 text-white/20" />
              Searching across all categories...
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export function IntelligenceOverlay() {
  return (
    <>
      <GlobalCommandPalette />
      <GlobalSearch />
    </>
  )
}