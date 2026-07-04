"use client"

import { useState, useMemo } from "react"
import {
  Building2,
  Plus,
  Search,
  Mail,
  X,
  Users,
  Check,
  Filter,
} from "lucide-react"

import { cn } from "@/utils/cn"
import { StatusBadge, DataTable, Modal, SectionHeader } from "./shared"

// ─── TYPES ─────────────────────────────────────────────────────────────────────

interface Organization {
  id: string
  name: string
  department: string
  tenant: string
  projects: number
  status: "active" | "inactive"
  created: string
}

// ─── MOCK DATA ─────────────────────────────────────────────────────────────────

const ORGANIZATIONS: Organization[] = [
  { id: "ORG-001", name: "Acme Corp", department: "Engineering", tenant: "acmecorp", projects: 12, status: "active", created: "2025-01-15" },
  { id: "ORG-002", name: "Globex Inc", department: "Security", tenant: "globex", projects: 8, status: "active", created: "2025-02-20" },
  { id: "ORG-003", name: "Initech", department: "IT Operations", tenant: "initech", projects: 5, status: "active", created: "2025-03-10" },
  { id: "ORG-004", name: "Umbrella Corp", department: "R&D", tenant: "umbrella", projects: 15, status: "active", created: "2024-11-01" },
  { id: "ORG-005", name: "Cyberdyne Systems", department: "AI Research", tenant: "cyberdyne", projects: 9, status: "active", created: "2025-04-22" },
  { id: "ORG-006", name: "Wayne Enterprises", department: "Defense", tenant: "wayne", projects: 20, status: "active", created: "2024-09-05" },
  { id: "ORG-007", name: "Stark Industries", department: "Engineering", tenant: "stark", projects: 18, status: "active", created: "2024-07-12" },
  { id: "ORG-008", name: "Oscorp", department: "Research", tenant: "oscorp", projects: 3, status: "inactive", created: "2025-05-30" },
]

const DEPARTMENTS = Array.from(new Set(ORGANIZATIONS.map((o) => o.department)))

const columns = [
  { label: "Org Name", key: "name" },
  { label: "ID", key: "id" },
  { label: "Department", key: "department" },
  { label: "Tenant", key: "tenant" },
  { label: "Projects", key: "projects" },
  {
    label: "Status",
    key: "status",
    render: (row: Organization) => (
      <StatusBadge tone={row.status === "active" ? "active" : "inactive"} label={row.status} />
    ),
  },
  { label: "Created", key: "created" },
]

// ─── COMPONENT ─────────────────────────────────────────────────────────────────

export default function OrganizationsPanel() {
  const [search, setSearch] = useState("")
  const [deptFilter, setDeptFilter] = useState<string>("All")
  const [showInvite, setShowInvite] = useState(false)

  const filtered = useMemo(() => {
    return ORGANIZATIONS.filter((org) => {
      const matchesSearch =
        !search ||
        org.name.toLowerCase().includes(search.toLowerCase()) ||
        org.id.toLowerCase().includes(search.toLowerCase()) ||
        org.department.toLowerCase().includes(search.toLowerCase())
      const matchesDept = deptFilter === "All" || org.department === deptFilter
      return matchesSearch && matchesDept
    })
  }, [search, deptFilter])

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Organizations"
        subtitle="Manage tenants and departments"
        actions={
          <button
            onClick={() => setShowInvite(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-[18px] bg-[#38B88A] text-white text-sm font-medium hover:bg-[#2F9F77] transition-colors duration-150"
          >
            <Plus className="w-4 h-4" />
            Invite Organization
          </button>
        }
      />

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#9CA3AF]" />
          <input
            type="text"
            placeholder="Search organizations..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-10 pl-10 pr-4 rounded-[18px] bg-white border border-[#E8EDF3] text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A] transition-all duration-150"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-[#6B7280]" />
          {["All", ...DEPARTMENTS].map((dept) => (
            <button
              key={dept}
              onClick={() => setDeptFilter(dept)}
              className={cn(
                "px-3 py-1.5 rounded-[18px] text-xs font-medium transition-colors duration-150",
                deptFilter === dept
                  ? "bg-[#38B88A] text-white"
                  : "bg-white border border-[#E8EDF3] text-[#6B7280] hover:text-[#111827] hover:bg-[#F4F7FA]",
              )}
            >
              {dept}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <DataTable columns={columns} data={filtered} idKey="id" />

      {/* Invite Modal */}
      {showInvite && (
        <Modal title="Invite Organization" onClose={() => setShowInvite(false)}>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-[#111827] block mb-1.5">Organization Name</label>
              <input
                type="text"
                placeholder="Enter organization name"
                className="w-full h-10 px-4 rounded-[18px] bg-[#F4F7FA] border border-[#E8EDF3] text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A]"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-[#111827] block mb-1.5">Department</label>
              <input
                type="text"
                placeholder="e.g. Engineering, Security"
                className="w-full h-10 px-4 rounded-[18px] bg-[#F4F7FA] border border-[#E8EDF3] text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A]"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-[#111827] block mb-1.5">Admin Email</label>
              <input
                type="email"
                placeholder="admin@company.com"
                className="w-full h-10 px-4 rounded-[18px] bg-[#F4F7FA] border border-[#E8EDF3] text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A]"
              />
            </div>
          </div>
          <div className="flex items-center justify-end gap-3 mt-6">
            <button
              onClick={() => setShowInvite(false)}
              className="px-4 py-2 rounded-[18px] text-sm font-medium text-[#6B7280] hover:bg-[#F4F7FA] hover:text-[#111827] border border-[#E8EDF3] transition-colors duration-150"
            >
              Cancel
            </button>
            <button
              onClick={() => setShowInvite(false)}
              className="flex items-center gap-2 px-4 py-2 rounded-[18px] bg-[#38B88A] text-white text-sm font-medium hover:bg-[#2F9F77] transition-colors duration-150"
            >
              <Mail className="w-4 h-4" />
              Send Invitation
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
