"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Bell,
  CheckCheck,
  CheckCircle,
  AlertTriangle,
  ShieldAlert,
  XCircle,
  RefreshCw,
  AlertOctagon,
  PlayCircle,
  Rocket,
  Award,
  X,
  Filter,
  ChevronRight,
  Clock,
} from "lucide-react"

type NotificationType =
  | "mission_completed"
  | "approval_required"
  | "security_alert"
  | "worker_error"
  | "connector_sync"
  | "runtime_warning"
  | "replay_ready"
  | "deployment_success"
  | "certification_passed"

type Priority = "critical" | "high" | "medium" | "low"

interface Notification {
  id: string
  type: NotificationType
  title: string
  description: string
  timestamp: Date
  read: boolean
  priority: Priority
}

const typeConfig: Record<NotificationType, { icon: React.ReactNode; label: string }> = {
  mission_completed: { icon: <CheckCircle size={16} />, label: "Mission Completed" },
  approval_required: { icon: <AlertTriangle size={16} />, label: "Approval Required" },
  security_alert: { icon: <ShieldAlert size={16} />, label: "Security Alert" },
  worker_error: { icon: <XCircle size={16} />, label: "Worker Error" },
  connector_sync: { icon: <RefreshCw size={16} />, label: "Connector Sync" },
  runtime_warning: { icon: <AlertOctagon size={16} />, label: "Runtime Warning" },
  replay_ready: { icon: <PlayCircle size={16} />, label: "Replay Ready" },
  deployment_success: { icon: <Rocket size={16} />, label: "Deployment" },
  certification_passed: { icon: <Award size={16} />, label: "Certification" },
}

const priorityColors: Record<Priority, string> = {
  critical: "bg-red-500",
  high: "bg-orange-500",
  medium: "bg-blue-500",
  low: "bg-gray-400",
}

const filterOptions = ["All", "Unread", "Priority"] as const
type FilterMode = (typeof filterOptions)[number]

function timeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000)
  if (seconds < 60) return "just now"
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

const mockNotifications: Notification[] = [
  { id: "n1", type: "mission_completed", title: "Data Pipeline ETL", description: "Mission completed successfully with 0 errors.", timestamp: new Date(Date.now() - 2 * 60 * 1000), read: false, priority: "low" },
  { id: "n2", type: "approval_required", title: "Deploy to Production", description: "User role escalation requires your approval.", timestamp: new Date(Date.now() - 5 * 60 * 1000), read: false, priority: "high" },
  { id: "n3", type: "security_alert", title: "Suspicious Login Detected", description: "New login from IP 203.0.113.42 in an unrecognized region.", timestamp: new Date(Date.now() - 12 * 60 * 1000), read: false, priority: "critical" },
  { id: "n4", type: "worker_error", title: "Worker node w-034 failed", description: "Worker crashed due to OOM. Auto-restart initiated.", timestamp: new Date(Date.now() - 18 * 60 * 1000), read: true, priority: "critical" },
  { id: "n5", type: "connector_sync", title: "Salesforce Sync Complete", description: "12,430 records synced in 34 seconds.", timestamp: new Date(Date.now() - 30 * 60 * 1000), read: false, priority: "medium" },
  { id: "n6", type: "runtime_warning", title: "Memory Threshold Exceeded", description: "Runtime memory at 87%. Consider scaling workers.", timestamp: new Date(Date.now() - 45 * 60 * 1000), read: true, priority: "high" },
  { id: "n7", type: "replay_ready", title: "Session Replay Available", description: "Session #9821 replay is ready for review.", timestamp: new Date(Date.now() - 60 * 60 * 1000), read: false, priority: "medium" },
  { id: "n8", type: "deployment_success", title: "v2.14.0 Deployed", description: "Deployed to staging environment. All health checks passed.", timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000), read: false, priority: "low" },
  { id: "n9", type: "certification_passed", title: "SOC 2 Audit Certified", description: "Annual SOC 2 Type II certification passed with no findings.", timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000), read: true, priority: "low" },
  { id: "n10", type: "mission_completed", title: "Knowledge Graph Update", description: "Graph updated with 8,421 new entity relationships.", timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000), read: false, priority: "medium" },
  { id: "n11", type: "worker_error", title: "GPU Worker Offline", description: "Worker w-gpu-007 went offline. Failover in progress.", timestamp: new Date(Date.now() - 5 * 60 * 60 * 1000), read: true, priority: "critical" },
  { id: "n12", type: "approval_required", title: "Cross-Origin Data Access", description: "Integration fabric request requires security approval.", timestamp: new Date(Date.now() - 6 * 60 * 60 * 1000), read: false, priority: "high" },
]

const itemVariants = {
  hidden: { opacity: 0, x: -12 },
  visible: (i: number) => ({
    opacity: 1,
    x: 0,
    transition: { delay: i * 0.03, type: "spring" as const, damping: 20, stiffness: 200 },
  }),
}

export default function NotificationCenter({ onClose }: { onClose?: () => void }) {
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState<Notification[]>(mockNotifications)
  const [filter, setFilter] = useState<FilterMode>("All")
  const panelRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)

  const unreadCount = useCallback(() => notifications.filter((n) => !n.read).length, [notifications])

  const filteredNotifications = useCallback(() => {
    switch (filter) {
      case "Unread":
        return notifications.filter((n) => !n.read)
      case "Priority":
        return notifications.filter((n) => n.priority === "critical" || n.priority === "high")
      default:
        return notifications
    }
  }, [filter, notifications])

  const markAsRead = useCallback((id: string) => {
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)))
  }, [])

  const markAllAsRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
  }, [])

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    const clickHandler = (e: MouseEvent) => {
      if (
        panelRef.current &&
        !panelRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setOpen(false)
      }
    }
    document.addEventListener("keydown", handler)
    document.addEventListener("mousedown", clickHandler)
    return () => {
      document.removeEventListener("keydown", handler)
      document.removeEventListener("mousedown", clickHandler)
    }
  }, [open])

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        onClick={() => setOpen((prev) => !prev)}
        className="relative flex h-9 w-9 items-center justify-center rounded-xl border border-[#E8EDF3] bg-white text-gray-600 transition-colors hover:bg-gray-50 hover:text-gray-900"
      >
        <Bell size={18} />
        {unreadCount() > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold leading-none text-white">
            {unreadCount() > 9 ? "9+" : unreadCount()}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            ref={panelRef}
            initial={{ opacity: 0, scale: 0.95, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -8 }}
            transition={{ type: "spring" as const, damping: 22, stiffness: 280 }}
            className="absolute right-0 top-full z-[9999] mt-2 w-[420px] max-w-[420px] overflow-hidden rounded-[18px] border border-[#E8EDF3] bg-white shadow-lg"
          >
            <div className="flex items-center justify-between border-b border-[#E8EDF3] px-5 py-4">
              <h2 className="text-[15px] font-semibold text-gray-900">Notifications</h2>
              <div className="flex items-center gap-2">
                {unreadCount() > 0 && (
                  <button
                    onClick={markAllAsRead}
                    className="flex items-center gap-1 rounded-lg px-2.5 py-1 text-[11px] font-medium text-blue-600 transition-colors hover:bg-blue-50"
                  >
                    <CheckCheck size={13} />
                    Mark all read
                  </button>
                )}
                <button
                  onClick={() => setOpen(false)}
                  className="flex h-6 w-6 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                >
                  <X size={14} />
                </button>
              </div>
            </div>

            <div className="flex items-center gap-2 border-b border-[#E8EDF3] px-5 py-3">
              <Filter size={14} className="text-gray-400" />
              {filterOptions.map((option) => (
                <button
                  key={option}
                  onClick={() => setFilter(option)}
                  className={`rounded-lg px-3 py-1 text-[12px] font-medium transition-colors ${
                    filter === option
                      ? "bg-blue-50 text-blue-700"
                      : "text-gray-500 hover:bg-gray-50 hover:text-gray-700"
                  }`}
                >
                  {option}
                </button>
              ))}
            </div>

            <div className="max-h-[400px] overflow-y-auto">
              {filteredNotifications().length === 0 && (
                <div className="flex flex-col items-center py-12 text-gray-400">
                  <CheckCircle size={28} className="mb-2 opacity-50" />
                  <p className="text-sm">All caught up!</p>
                </div>
              )}

              {filteredNotifications().map((notification, idx) => {
                const config = typeConfig[notification.type]
                return (
                  <motion.div
                    key={notification.id}
                    custom={idx}
                    variants={itemVariants}
                    initial="hidden"
                    animate="visible"
                    className={`group relative border-b border-[#E8EDF3]/60 px-5 py-3.5 transition-colors last:border-b-0 hover:bg-gray-50/80 ${
                      !notification.read ? "bg-blue-50/30" : ""
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className="relative mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-500">
                        {config.icon}
                        <span
                          className={`absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-white ${
                            priorityColors[notification.priority]
                          }`}
                        />
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p
                              className={`text-[13px] leading-tight ${
                                !notification.read ? "font-semibold text-gray-900" : "font-medium text-gray-700"
                              }`}
                            >
                              {notification.title}
                            </p>
                            <p className="mt-0.5 text-[12px] leading-tight text-gray-500 line-clamp-2">
                              {notification.description}
                            </p>
                          </div>
                          <div className="flex shrink-0 items-center gap-1.5">
                            <span className="whitespace-nowrap text-[11px] text-gray-400">
                              {timeAgo(notification.timestamp)}
                            </span>
                            <span
                              className={`h-1.5 w-1.5 rounded-full ${
                                notification.read ? "bg-transparent" : "bg-blue-500"
                              }`}
                            />
                          </div>
                        </div>

                        <div className="mt-2 flex items-center gap-2">
                          <span className="rounded-md bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-500">
                            {config.label}
                          </span>
                          <span
                            className={`rounded-md px-2 py-0.5 text-[10px] font-medium capitalize ${
                              notification.priority === "critical"
                                ? "bg-red-50 text-red-600"
                                : notification.priority === "high"
                                  ? "bg-orange-50 text-orange-600"
                                  : notification.priority === "medium"
                                    ? "bg-blue-50 text-blue-600"
                                    : "bg-gray-50 text-gray-500"
                            }`}
                          >
                            {notification.priority}
                          </span>
                        </div>
                      </div>

                      {!notification.read && (
                        <button
                          onClick={() => markAsRead(notification.id)}
                          className="absolute right-3 top-3 flex h-6 w-6 items-center justify-center rounded-lg text-gray-300 opacity-0 transition-opacity hover:bg-gray-100 hover:text-gray-600 group-hover:opacity-100"
                          title="Mark as read"
                        >
                          <CheckCheck size={14} />
                        </button>
                      )}
                    </div>
                  </motion.div>
                )
              })}
            </div>

            <button className="flex w-full items-center justify-center gap-1 border-t border-[#E8EDF3] px-5 py-3 text-[13px] font-medium text-blue-600 transition-colors hover:bg-blue-50">
              View All
              <ChevronRight size={14} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}