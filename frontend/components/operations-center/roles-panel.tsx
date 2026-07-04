"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Plus,
  ShieldCheck,
  ChevronDown,
  ChevronRight,
  ToggleLeft,
  ToggleRight,
  Users,
  Lock,
  FileText,
} from "lucide-react"

import { cn } from "@/utils/cn"
import { StatusBadge, DataTable, Modal, SectionHeader } from "./shared"

// ─── TYPES ─────────────────────────────────────────────────────────────────────

interface Permission {
  id: string
  label: string
  enabled: boolean
}

interface Role {
  id: string
  name: string
  type: "RBAC" | "ABAC"
  usersCount: number
  permissionsCount: number
  created: string
  permissions: Permission[]
}

// ─── MOCK DATA ─────────────────────────────────────────────────────────────────

const PREDEFINED_PERMISSIONS: Record<string, Permission[]> = {
  admin: [
    { id: "perm-1", label: "missions.execute", enabled: true },
    { id: "perm-2", label: "missions.cancel", enabled: true },
    { id: "perm-3", label: "users.manage", enabled: true },
    { id: "perm-4", label: "roles.manage", enabled: true },
    { id: "perm-5", label: "connectors.configure", enabled: true },
    { id: "perm-6", label: "secrets.read", enabled: true },
    { id: "perm-7", label: "secrets.write", enabled: true },
    { id: "perm-8", label: "audit.view", enabled: true },
    { id: "perm-9", label: "backup.create", enabled: true },
    { id: "perm-10", label: "backup.restore", enabled: true },
  ],
  analyst: [
    { id: "perm-11", label: "missions.execute", enabled: true },
    { id: "perm-12", label: "missions.view", enabled: true },
    { id: "perm-13", label: "audit.view", enabled: true },
    { id: "perm-14", label: "models.view", enabled: true },
    { id: "perm-15", label: "connectors.view", enabled: false },
    { id: "perm-16", label: "secrets.read", enabled: false },
  ],
  operator: [
    { id: "perm-17", label: "missions.execute", enabled: true },
    { id: "perm-18", label: "missions.cancel", enabled: true },
    { id: "perm-19", label: "workers.manage", enabled: true },
    { id: "perm-20", label: "connectors.view", enabled: true },
    { id: "perm-21", label: "runtime.view", enabled: true },
    { id: "perm-22", label: "users.view", enabled: false },
  ],
  viewer: [
    { id: "perm-23", label: "missions.view", enabled: true },
    { id: "perm-24", label: "audit.view", enabled: true },
    { id: "perm-25", label: "models.view", enabled: true },
    { id: "perm-26", label: "runtime.view", enabled: true },
    { id: "perm-27", label: "connectors.view", enabled: false },
  ],
  custom: [
    { id: "perm-28", label: "missions.execute", enabled: false },
    { id: "perm-29", label: "users.view", enabled: false },
    { id: "perm-30", label: "connectors.view", enabled: false },
    { id: "perm-31", label: "secrets.read", enabled: false },
  ],
}

const ROLES: Role[] = [
  { id: "ROLE-001", name: "Admin", type: "RBAC", usersCount: 5, permissionsCount: 10, created: "2024-06-01", permissions: PREDEFINED_PERMISSIONS.admin },
  { id: "ROLE-002", name: "Analyst", type: "RBAC", usersCount: 12, permissionsCount: 6, created: "2024-06-15", permissions: PREDEFINED_PERMISSIONS.analyst },
  { id: "ROLE-003", name: "Operator", type: "RBAC", usersCount: 8, permissionsCount: 6, created: "2024-07-01", permissions: PREDEFINED_PERMISSIONS.operator },
  { id: "ROLE-004", name: "Viewer", type: "RBAC", usersCount: 23, permissionsCount: 5, created: "2024-07-20", permissions: PREDEFINED_PERMISSIONS.viewer },
  { id: "ROLE-005", name: "Custom", type: "ABAC", usersCount: 0, permissionsCount: 4, created: "2025-01-10", permissions: PREDEFINED_PERMISSIONS.custom },
]

const columns = [
  { label: "Name", key: "name" },
  { label: "Type", key: "type", render: (row: Role) => <StatusBadge tone={row.type === "RBAC" ? "active" : "warning"} label={row.type} /> },
  { label: "Users", key: "usersCount" },
  { label: "Permissions", key: "permissionsCount" },
  { label: "Created", key: "created" },
]

// ─── COMPONENT ─────────────────────────────────────────────────────────────────

export default function RolesPanel() {
  const [expandedRole, setExpandedRole] = useState<string | null>(null)
  const [roles, setRoles] = useState(ROLES)
  const [showCreate, setShowCreate] = useState(false)

  const togglePermission = (roleId: string, permId: string) => {
    setRoles((prev) =>
      prev.map((r) =>
        r.id === roleId
          ? { ...r, permissions: r.permissions.map((p) => (p.id === permId ? { ...p, enabled: !p.enabled } : p)) }
          : r,
      ),
    )
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Roles & Permissions"
        subtitle="Define access control roles and their permissions"
        actions={
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-[18px] bg-[#38B88A] text-white text-sm font-medium hover:bg-[#2F9F77] transition-colors duration-150"
          >
            <Plus className="w-4 h-4" />
            Create Role
          </button>
        }
      />

      {/* Templates */}
      <div className="flex flex-wrap gap-2">
        {["Admin", "Analyst", "Operator", "Viewer", "Custom"].map((tpl) => (
          <button
            key={tpl}
            onClick={() => {
              const found = roles.find((r) => r.name === tpl)
              if (found) setExpandedRole(expandedRole === found.id ? null : found.id)
            }}
            className="flex items-center gap-2 px-3 py-2 rounded-[18px] bg-white border border-[#E8EDF3] text-xs font-medium text-[#6B7280] hover:text-[#111827] hover:bg-[#F4F7FA] transition-colors duration-150"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-[#38B88A]" />
            {tpl}
          </button>
        ))}
      </div>

      {/* Roles Table */}
      <div className="border border-[#E8EDF3] bg-white rounded-[18px] overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#E8EDF3] bg-[#F4F7FA]">
              {columns.map((col) => (
                <th key={col.key} className="px-4 py-3 text-left text-xs font-semibold text-[#6B7280] uppercase tracking-wider">{col.label}</th>
              ))}
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#6B7280] uppercase tracking-wider"></th>
            </tr>
          </thead>
          <tbody>
            {roles.map((role) => (
              <>
                <tr
                  key={role.id}
                  onClick={() => setExpandedRole(expandedRole === role.id ? null : role.id)}
                  className="border-b border-[#E8EDF3] cursor-pointer hover:bg-[#F4F7FA] transition-colors duration-100"
                >
                  {columns.map((col) => (
                    <td key={col.key} className="px-4 py-3 text-[#111827] whitespace-nowrap">
                      {col.render ? col.render(role) : (role as any)[col.key] ?? "-"}
                    </td>
                  ))}
                  <td className="px-4 py-3 text-right">
                    {expandedRole === role.id ? (
                      <ChevronDown className="w-4 h-4 text-[#38B88A] inline" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-[#9CA3AF] inline" />
                    )}
                  </td>
                </tr>
                {expandedRole === role.id && (
                  <tr key={`${role.id}-perms`}>
                    <td colSpan={columns.length + 1} className="px-6 py-4 bg-[#F4F7FA]">
                      <div className="space-y-2">
                        <p className="text-xs font-semibold text-[#6B7280] uppercase tracking-wider mb-3">Permissions</p>
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                          {role.permissions.map((perm) => (
                            <label
                              key={perm.id}
                              className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white border border-[#E8EDF3] cursor-pointer hover:border-[#38B88A]/50 transition-colors duration-150"
                            >
                              <button
                                onClick={(e) => { e.stopPropagation(); togglePermission(role.id, perm.id) }}
                                className={cn(
                                  "w-8 h-5 rounded-full flex items-center transition-all duration-200",
                                  perm.enabled ? "bg-[#38B88A] justify-end" : "bg-[#D1D5DB] justify-start",
                                )}
                              >
                                <div className="w-3.5 h-3.5 rounded-full bg-white shadow-sm mx-0.5" />
                              </button>
                              <span className="text-xs font-mono text-[#111827]">{perm.label}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create Role Modal */}
      {showCreate && (
        <Modal title="Create Role" onClose={() => setShowCreate(false)}>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-[#111827] block mb-1.5">Role Name</label>
              <input type="text" placeholder="e.g. Security Auditor" className="w-full h-10 px-4 rounded-[18px] bg-[#F4F7FA] border border-[#E8EDF3] text-sm focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A]" />
            </div>
            <div>
              <label className="text-sm font-medium text-[#111827] block mb-1.5">Type</label>
              <select className="w-full h-10 px-4 rounded-[18px] bg-[#F4F7FA] border border-[#E8EDF3] text-sm text-[#111827] focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A]">
                <option>RBAC</option>
                <option>ABAC</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-[#111827] block mb-1.5">Description</label>
              <textarea rows={3} placeholder="Role description..." className="w-full px-4 py-2 rounded-[18px] bg-[#F4F7FA] border border-[#E8EDF3] text-sm focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A] resize-none" />
            </div>
          </div>
          <div className="flex items-center justify-end gap-3 mt-6">
            <button onClick={() => setShowCreate(false)} className="px-4 py-2 rounded-[18px] text-sm font-medium text-[#6B7280] hover:bg-[#F4F7FA] hover:text-[#111827] border border-[#E8EDF3] transition-colors">Cancel</button>
            <button onClick={() => setShowCreate(false)} className="px-4 py-2 rounded-[18px] bg-[#38B88A] text-white text-sm font-medium hover:bg-[#2F9F77] transition-colors">Create Role</button>
          </div>
        </Modal>
      )}
    </div>
  )
}