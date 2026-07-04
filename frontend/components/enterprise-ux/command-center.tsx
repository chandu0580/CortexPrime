"use client"

import { useState, useEffect, useCallback, useRef, useMemo } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import {
  LayoutDashboard,
  Cpu,
  Users,
  Target,
  Mic,
  Database,
  Briefcase,
  HeadphonesIcon,
  Globe,
  Repeat,
  Repeat2,
  BarChart3,
  ShieldCheck,
  Activity,
  Puzzle,
  Settings,
  Code2,
  Building2,
  PlayCircle,
  History,
  HeartPulse,
  List,
  FileText,
  ExternalLink,
  UserPlus,
  Eye,
  Command,
  Search,
  ArrowRight,
  Clock,
} from "lucide-react"

interface CommandItem {
  id: string
  label: string
  icon: React.ReactNode
  category: "Pages" | "Commands" | "Missions" | "Actions"
  route?: string
  action?: () => void
}

interface RecentSearch {
  label: string
  category: string
}

const pages: CommandItem[] = [
  { id: "cmd", label: "Command", icon: <Command size={16} />, category: "Pages", route: "/command" },
  { id: "runtime", label: "Runtime", icon: <Cpu size={16} />, category: "Pages", route: "/runtime" },
  { id: "agents", label: "Agents", icon: <Users size={16} />, category: "Pages", route: "/agents" },
  { id: "missions", label: "Missions", icon: <Target size={16} />, category: "Pages", route: "/missions" },
  { id: "voice", label: "Voice", icon: <Mic size={16} />, category: "Pages", route: "/voice" },
  { id: "memory", label: "Memory", icon: <Database size={16} />, category: "Pages", route: "/memory" },
  { id: "workspace", label: "Workspace", icon: <Briefcase size={16} />, category: "Pages", route: "/workspace" },
  { id: "operator", label: "Operator", icon: <HeadphonesIcon size={16} />, category: "Pages", route: "/operator" },
  { id: "browser", label: "Browser", icon: <Globe size={16} />, category: "Pages", route: "/browser" },
  { id: "replay", label: "Replay", icon: <Repeat size={16} />, category: "Pages", route: "/replay" },
  { id: "enterprise-replay", label: "Enterprise Replay", icon: <Repeat2 size={16} />, category: "Pages", route: "/enterprise-replay" },
  { id: "analytics", label: "Analytics", icon: <BarChart3 size={16} />, category: "Pages", route: "/analytics" },
  { id: "governance", label: "Governance", icon: <ShieldCheck size={16} />, category: "Pages", route: "/governance" },
  { id: "system-status", label: "System Status", icon: <Activity size={16} />, category: "Pages", route: "/system-status" },
  { id: "integrations", label: "Integrations", icon: <Puzzle size={16} />, category: "Pages", route: "/integrations" },
  { id: "settings", label: "Settings", icon: <Settings size={16} />, category: "Pages", route: "/settings" },
  { id: "developer-portal", label: "Developer Portal", icon: <Code2 size={16} />, category: "Pages", route: "/developer-portal" },
  { id: "operations-center", label: "Operations Center", icon: <Building2 size={16} />, category: "Pages", route: "/operations-center" },
]

const commands: CommandItem[] = [
  { id: "execute-mission", label: "Execute Mission", icon: <PlayCircle size={16} />, category: "Commands", action: () => {} },
  { id: "run-replay", label: "Run Replay", icon: <History size={16} />, category: "Commands", action: () => {} },
  { id: "check-health", label: "Check Health", icon: <HeartPulse size={16} />, category: "Commands", action: () => {} },
  { id: "list-workers", label: "List Workers", icon: <List size={16} />, category: "Commands", action: () => {} },
  { id: "view-audit", label: "View Audit", icon: <FileText size={16} />, category: "Commands", action: () => {} },
  { id: "open-dashboard", label: "Open Dashboard", icon: <ExternalLink size={16} />, category: "Commands", route: "/dashboard" },
  { id: "create-user", label: "Create User", icon: <UserPlus size={16} />, category: "Commands", action: () => {} },
  { id: "view-models", label: "View Models", icon: <Eye size={16} />, category: "Commands", action: () => {} },
]

const allItems = [...pages, ...commands]

const categoryOrder = ["Pages", "Commands", "Missions", "Actions"] as const

const overlayVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
}

const panelVariants = {
  hidden: { opacity: 0, scale: 0.95, y: -20 },
  visible: { opacity: 1, scale: 1, y: 0, transition: { type: "spring" as const, damping: 25, stiffness: 300 } },
}

export default function CommandCenter({ onClose }: { onClose?: () => void }) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [recentSearches, setRecentSearches] = useState<RecentSearch[]>([
    { label: "Runtime", category: "Pages" },
    { label: "Check Health", category: "Commands" },
    { label: "Missions", category: "Pages" },
  ])

  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        setOpen((prev) => !prev)
      }
      if (e.key === "Escape" && open) {
        e.preventDefault()
        setOpen(false)
      }
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [open])

  useEffect(() => {
    if (open) {
      setQuery("")
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  const groupedResults = useMemo(() => {
    const lower = query.toLowerCase().trim()
    if (!lower) return [] as { category: string; items: CommandItem[] }[]

    const filtered = allItems.filter(
      (item) =>
        item.label.toLowerCase().includes(lower)
    )

    const groups: { category: string; items: CommandItem[] }[] = []
    for (const cat of categoryOrder) {
      const matches = filtered.filter((item) => item.category === cat)
      if (matches.length > 0) {
        groups.push({ category: cat, items: matches })
      }
    }
    return groups
  }, [query])

  const flatResults = useMemo(() => {
    return groupedResults.flatMap((g) => g.items)
  }, [groupedResults])

  const executeItem = useCallback(
    (item: CommandItem) => {
      const search: RecentSearch = { label: item.label, category: item.category }
      setRecentSearches((prev) => {
        const filtered = prev.filter((s) => s.label !== item.label)
        return [search, ...filtered].slice(0, 5)
      })

      if (item.route) {
        router.push(item.route)
      } else if (item.action) {
        item.action()
      }
      setOpen(false)
    },
    [router]
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault()
        setSelectedIndex((prev) => (prev + 1) % flatResults.length)
      } else if (e.key === "ArrowUp") {
        e.preventDefault()
        setSelectedIndex((prev) => (prev - 1 + flatResults.length) % flatResults.length)
      } else if (e.key === "Enter" && flatResults[selectedIndex]) {
        e.preventDefault()
        executeItem(flatResults[selectedIndex])
      }
    },
    [flatResults, selectedIndex, executeItem]
  )

  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  useEffect(() => {
    const selected = listRef.current?.querySelector(`[data-index="${selectedIndex}"]`)
    selected?.scrollIntoView({ block: "nearest" })
  }, [selectedIndex])

  const handleBackdropClick = useCallback((e: React.MouseEvent) => {
    if (e.target === e.currentTarget) setOpen(false)
  }, [])

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[9999] flex items-start justify-center bg-black/40 pt-[12vh] backdrop-blur-sm"
          variants={overlayVariants}
          initial="hidden"
          animate="visible"
          exit="hidden"
          onClick={handleBackdropClick}
        >
          <motion.div
            className="w-full max-w-2xl overflow-hidden rounded-[18px] border border-[#E8EDF3] bg-white shadow-xl"
            variants={panelVariants}
            initial="hidden"
            animate="visible"
            exit="hidden"
          >
            <div className="flex items-center gap-3 border-b border-[#E8EDF3] px-5 py-4">
              <Search size={18} className="text-gray-400 shrink-0" />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Search pages, commands, missions..."
                className="flex-1 bg-transparent text-[15px] text-gray-900 outline-none placeholder:text-gray-400"
              />
              <kbd className="hidden shrink-0 rounded-md border border-[#E8EDF3] bg-gray-50 px-2 py-0.5 text-[11px] font-medium text-gray-400 sm:inline-block">
                ESC
              </kbd>
            </div>

            <div ref={listRef} className="max-h-[420px] overflow-y-auto px-2 py-2">
              {query.trim() && groupedResults.length === 0 && (
                <div className="flex flex-col items-center py-12 text-gray-400">
                  <Search size={32} className="mb-2 opacity-50" />
                  <p className="text-sm">No results found for "{query}"</p>
                </div>
              )}

              {groupedResults.map((group) => (
                <div key={group.category}>
                  <div className="px-3 py-2 text-[11px] font-semibold uppercase tracking-widest text-gray-400">
                    {group.category}
                  </div>
                  {group.items.map((item) => {
                    const idx = flatResults.indexOf(item)
                    const isSelected = idx === selectedIndex
                    return (
                      <button
                        key={item.id}
                        data-index={idx}
                        onClick={() => executeItem(item)}
                        className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition-colors ${
                          isSelected
                            ? "bg-blue-50 text-blue-700"
                            : "text-gray-700 hover:bg-gray-50"
                        }`}
                      >
                        <span
                          className={`flex h-7 w-7 items-center justify-center rounded-lg ${
                            isSelected ? "bg-blue-100 text-blue-600" : "bg-gray-100 text-gray-500"
                          }`}
                        >
                          {item.icon}
                        </span>
                        <span className="flex-1 font-medium">{item.label}</span>
                        {item.route && (
                          <ArrowRight size={14} className="text-gray-300" />
                        )}
                      </button>
                    )
                  })}
                </div>
              ))}

              {!query.trim() && (
                <div className="px-3 pb-1">
                  <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-widest text-gray-400">
                    <Clock size={12} />
                    Recent Searches
                  </div>
                  {recentSearches.map((search) => (
                    <button
                      key={search.label}
                      onClick={() => setQuery(search.label)}
                      className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm text-gray-500 hover:bg-gray-50 transition-colors"
                    >
                      <History size={14} className="text-gray-300" />
                      <span>{search.label}</span>
                      <span className="ml-auto text-[11px] text-gray-300">{search.category}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-center gap-4 border-t border-[#E8EDF3] px-5 py-3 text-[11px] text-gray-400">
              <span className="flex items-center gap-1">
                <kbd className="rounded border border-[#E8EDF3] px-1.5 py-0.5 text-[10px]">↑↓</kbd>
                Navigate
              </span>
              <span className="flex items-center gap-1">
                <kbd className="rounded border border-[#E8EDF3] px-1.5 py-0.5 text-[10px]">↵</kbd>
                Select
              </span>
              <span className="flex items-center gap-1">
                <kbd className="rounded border border-[#E8EDF3] px-1.5 py-0.5 text-[10px]">Esc</kbd>
                Close
              </span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}