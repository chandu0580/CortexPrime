"use client"

import { useState, useMemo } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Plus,
  Search,
  Mail,
  Filter,
  ShieldCheck,
  X,
  User,
  Clock,
  CheckCircle,
  XCircle,
} from "lucide-react"

import { cn } from "@/utils/cn"
import { StatusBadge, DataTable, Modal, SectionHeader } from "./shared"

// ─── TYPES ─────────────────────────────────────────────────────────────────────

interface UserData {
  id: string
  name: string
  email: string
  role: string
  status: "active" | "inactive"
  mfa: "enabled" | "disabled"
  lastLogin: string
  groups: string[]
}

// ─── MOCK DATA ─────────────────────────────────────────────────────────────────

const MOCK_USERS: UserData[] = [
  { id: "USR-001", name: "Alice Johnson", email: "alice@acmecorp.com", role: "Admin", status: "active", mfa: "enabled", lastLogin: "2026-07-04 08:30", groups: ["Engineering", "Security"] },
  { id: "USR-002", name: "Bob Smith", email: "bob@globex.io", role: "Analyst", status: "active", mfa: "enabled", lastLogin: "2026-07-03 16:45", groups: ["Security"] },
  { id: "USR-003", name: "Carol Williams", email: "carol@initech.com", role: "Operator", status: "active", mfa: "disabled", lastLogin: "2026-07-04 07:15", groups: ["IT Operations"] },
  { id: "USR-004", name: "Dave Brown", email: "dave@umbrella.org", role: "Viewer", status: "active", mfa: "enabled", lastLogin: "2026-07-02 11:20", groups: ["R&D"] },
  { id: "USR-005", name: "Eve Davis", email: "eve@cyberdyne.ai", role: "Admin", status: "active", mfa: "enabled", lastLogin: "2026-07-04 09:00", groups: ["AI Research"] },
  { id: "USR-006", name: "Frank Miller", email: "frank@wayne.ent", role: "Analyst", status: "inactive", mfa: "disabled", lastLogin: "2026-06-15 14:30", groups: ["Defense"] },
  { id: "USR-007", name: "Grace Wilson", email: "grace@stark.ind", role: "Operator", status: "active", mfa: "enabled", lastLogin: "2026-07-04 06:50", groups: ["Engineering"] },
  { id: "USR-008", name: "Henry Taylor", email: "henry@oscorp.lab", role: "Viewer", status: "active", mfa: "disabled", lastLogin: "2026-07-01 10:00", groups: ["Research"] },
  { id: "USR-009", name: "Ivy Anderson", email: "ivy@acmecorp.com", role: "Operator", status: "active", mfa: "enabled", lastLogin: "2026-07-04 08:55", groups: ["Engineering"] },
  { id: "USR-010", name: "Jack Thomas", email: "jack@globex.io", role: "Analyst", status: "inactive", mfa: "disabled", lastLogin: "2026-06-20 09:10", groups: ["Security"] },
]

const ROLES = ["All", "Admin", "Analyst", "Operator", "Viewer"]
const STATUSES = ["All", "active", "inactive"]

const columns = [
  { label: "Name", key: "name" },
  { label: "Email", key: "email" },
  { label: "Role", key: "role" },
  {
    label: "Status",
    key: "status",
    render: (row: UserData) => (
      <StatusBadge tone={row.status === "active" ? "active" : "inactive"} label={row.status} />
    ),
  },
  {
    label: "MFA",
    key: "mfa",
    render: (row: UserData) => (
      <span className={cn("inline-flex items-center gap-1 text-xs font-medium", row.mfa === "enabled" ? "text-[#38B88A]" : "text-[#9CA3AF]")}>
        {row.mfa === "enabled" ? <CheckCircle className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
        {row.mfa}
      </span>
    ),
  },
  { label: "Last Login", key: "lastLogin" },
  {
    label: "Groups",
    key: "groups",
    render: (row: UserData) => (
      <div className="flex gap-1">
        {row.groups.map((g) => (
          <span key={g} className="px-2 py-0.5 rounded-full bg-[#F4F7FA] text-[10px] font-medium text-[#6B7280]">
            {g}
          </span>
        ))}
      </div>
    ),
  },
]

// ─── COMPONENT ─────────────────────────────────────────────────────────────────

export default function UsersPanel() {
  const [search, setSearch] = useState("")
  const [roleFilter, setRoleFilter] = useState("All")
  const [statusFilter, setStatusFilter] = useState("All")
  const [selectedUser, setSelectedUser] = useState<UserData | null>(null)
  const [showInvite, setShowInvite] = useState(false)

  const filtered = useMemo(() => {
    return MOCK_USERS.filter((u) => {
      const matchesSearch = !search || u.name.toLowerCase().includes(search.toLowerCase()) || u.email.toLowerCase().includes(search.toLowerCase())
      const matchesRole = roleFilter === "All" || u.role === roleFilter
      const matchesStatus = statusFilter === "All" || u.status === statusFilter
      return matchesSearch && matchesRole && matchesStatus
    })
  }, [search, roleFilter, statusFilter])

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Users"
        subtitle="Manage user accounts and access"
        actions={
          <button
            onClick={() => setShowInvite(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-[18px] bg-[#38B88A] text-white text-sm font-medium hover:bg-[#2F9F77] transition-colors duration-150"
          >
            <Plus className="w-4 h-4" />
            Invite User
          </button>
        }
      />

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#9CA3AF]" />
          <input
            type="text"
            placeholder="Search users..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-10 pl-10 pr-4 rounded-[18px] bg-white border border-[#E8EDF3] text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A] transition-all duration-150"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-[#6B7280]" />
          {ROLES.map((role) => (
            <button
              key={role}
              onClick={() => setRoleFilter(role)}
              className={cn(
                "px-3 py-1.5 rounded-[18px] text-xs font-medium transition-colors duration-150",
                roleFilter === role
                  ? "bg-[#38B88A] text-white"
                  : "bg-white border border-[#E8EDF3] text-[#6B7280] hover:text-[#111827] hover:bg-[#F4F7FA]",
              )}
            >
              {role}
            </button>
          ))}
          <div className="w-px h-6 bg-[#E8EDF3] mx-1" />
          {STATUSES.map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={cn(
                "px-3 py-1.5 rounded-[18px] text-xs font-medium transition-colors duration-150",
                statusFilter === st
                  ? "bg-[#38B88A] text-white"
                  : "bg-white border border-[#E8EDF3] text-[#6B7280] hover:text-[#111827] hover:bg-[#F4F7FA]",
              )}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <DataTable columns={columns} data={filtered} idKey="id" onRowClick={setSelectedUser} selectedId={selectedUser?.id} />

      {/* User Detail Modal */}
      <AnimatePresence>
        {selectedUser && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSelectedUser(null)}
          >
            <motion.div
              className="bg-white rounded-[18px] shadow-xl w-full max-w-md p-6"
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.2 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-full bg-[#38B88A] flex items-center justify-center text-white font-bold text-lg">
                    {selectedUser.name.split(" ").map((n) => n[0]).join("")}
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-[#111827]">{selectedUser.name}</h3>
                    <p className="text-sm text-[#6B7280]">{selectedUser.email}</p>
                  </div>
                </div>
                <button onClick={() => setSelectedUser(null)} className="p-1.5 rounded-lg text-[#6B7280] hover:bg-[#F4F7FA] transition-colors">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="space-y-3 text-sm border-t border-[#E8EDF3] pt-4">
                <div className="flex justify-between"><span className="text-[#6B7280]">User ID</span><span className="font-medium text-[#111827]">{selectedUser.id}</span></div>
                <div className="flex justify-between"><span className="text-[#6B7280]">Role</span><span className="font-medium text-[#111827]">{selectedUser.role}</span></div>
                <div className="flex justify-between"><span className="text-[#6B7280]">Status</span><StatusBadge tone={selectedUser.status === "active" ? "active" : "inactive"} label={selectedUser.status} /></div>
                <div className="flex justify-between"><span className="text-[#6B7280]">MFA</span><span className={cn("font-medium", selectedUser.mfa === "enabled" ? "text-[#38B88A]" : "text-[#9CA3AF]")}>{selectedUser.mfa}</span></div>
                <div className="flex justify-between"><span className="text-[#6B7280]">Last Login</span><span className="font-medium text-[#111827]">{selectedUser.lastLogin}</span></div>
                <div className="flex justify-between"><span className="text-[#6B7280]">Groups</span><span className="font-medium text-[#111827]">{selectedUser.groups.join(", ")}</span></div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Invite Modal */}
      {showInvite && (
        <Modal title="Invite User" onClose={() => setShowInvite(false)}>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-[#111827] block mb-1.5">Name</label>
              <input type="text" placeholder="Full name" className="w-full h-10 px-4 rounded-[18px] bg-[#F4F7FA] border border-[#E8EDF3] text-sm focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A]" />
            </div>
            <div>
              <label className="text-sm font-medium text-[#111827] block mb-1.5">Email</label>
              <input type="email" placeholder="user@company.com" className="w-full h-10 px-4 rounded-[18px] bg-[#F4F7FA] border border-[#E8EDF3] text-sm focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A]" />
            </div>
            <div>
              <label className="text-sm font-medium text-[#111827] block mb-1.5">Role</label>
              <select className="w-full h-10 px-4 rounded-[18px] bg-[#F4F7FA] border border-[#E8EDF3] text-sm text-[#111827] focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A]">
                <option>Admin</option>
                <option>Analyst</option>
                <option>Operator</option>
                <option>Viewer</option>
              </select>
            </div>
          </div>
          <div className="flex items-center justify-end gap-3 mt-6">
            <button onClick={() => setShowInvite(false)} className="px-4 py-2 rounded-[18px] text-sm font-medium text-[#6B7280] hover:bg-[#F4F7FA] hover:text-[#111827] border border-[#E8EDF3] transition-colors">Cancel</button>
            <button onClick={() => setShowInvite(false)} className="flex items-center gap-2 px-4 py-2 rounded-[18px] bg-[#38B88A] text-white text-sm font-medium hover:bg-[#2F9F77] transition-colors">
              <Mail className="w-4 h-4" />
              Send Invitation
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
