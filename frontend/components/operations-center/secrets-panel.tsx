"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import {
  Key,
  Plus,
  RotateCcw,
  AlertTriangle,
  CheckCircle,
  Clock,
  Lock,
  Eye,
  EyeOff,
} from "lucide-react"

import { cn } from "@/utils/cn"
import { StatusBadge, DataTable, Modal, SectionHeader } from "./shared"

// ─── TYPES ─────────────────────────────────────────────────────────────────────

interface Secret {
  id: string
  name: string
  provider: "Vault" | "Azure" | "AWS"
  status: "active" | "expiring" | "expired"
  lastRotation: string
  expiry: string
  created: string
}

// ─── MOCK DATA ─────────────────────────────────────────────────────────────────

const SECRETS: Secret[] = [
  { id: "SEC-001", name: "openai-api-key", provider: "Vault", status: "active", lastRotation: "2026-06-01", expiry: "2027-06-01", created: "2025-06-01" },
  { id: "SEC-002", name: "github-pat", provider: "Vault", status: "active", lastRotation: "2026-05-15", expiry: "2027-05-15", created: "2025-01-10" },
  { id: "SEC-003", name: "azure-connection-string", provider: "Azure", status: "expiring", lastRotation: "2026-01-20", expiry: "2026-07-20", created: "2024-07-20" },
  { id: "SEC-004", name: "aws-access-key", provider: "AWS", status: "active", lastRotation: "2026-06-10", expiry: "2027-06-10", created: "2025-06-10" },
  { id: "SEC-005", name: "jira-api-token", provider: "Vault", status: "active", lastRotation: "2026-04-01", expiry: "2027-04-01", created: "2024-04-01" },
  { id: "SEC-006", name: "slack-webhook-url", provider: "Vault", status: "expiring", lastRotation: "2025-12-15", expiry: "2026-07-15", created: "2024-12-15" },
  { id: "SEC-007", name: "azure-storage-key", provider: "Azure", status: "active", lastRotation: "2026-03-22", expiry: "2027-03-22", created: "2025-03-22" },
  { id: "SEC-008", name: "aws-secret-key", provider: "AWS", status: "expired", lastRotation: "2024-12-01", expiry: "2026-06-01", created: "2023-12-01" },
]

const columns = [
  {
    label: "Name",
    key: "name",
    render: (row: Secret) => (
      <div className="flex items-center gap-2">
        <Key className="w-3.5 h-3.5 text-[#6B7280]" />
        <span className="font-mono text-xs font-medium text-[#111827]">{row.name}</span>
      </div>
    ),
  },
  { label: "Provider", key: "provider", render: (row: Secret) => <StatusBadge tone={row.provider === "Vault" ? "active" : row.provider === "Azure" ? "healthy" : "warning"} label={row.provider} /> },
  {
    label: "Status",
    key: "status",
    render: (row: Secret) => {
      const toneMap: Record<string, "active" | "warning" | "error"> = { active: "active", expiring: "warning", expired: "error" }
      return <StatusBadge tone={toneMap[row.status]} label={row.status} />
    },
  },
  { label: "Last Rotation", key: "lastRotation" },
  {
    label: "Expiry",
    key: "expiry",
    render: (row: Secret) => (
      <div className="flex items-center gap-1.5">
        <span className={cn(row.status === "expiring" ? "text-[#F59E0B]" : row.status === "expired" ? "text-[#EF4444]" : "text-[#111827]")}>{row.expiry}</span>
        {row.status === "expiring" && <AlertTriangle className="w-3.5 h-3.5 text-[#F59E0B]" />}
        {row.status === "expired" && <AlertTriangle className="w-3.5 h-3.5 text-[#EF4444]" />}
      </div>
    ),
  },
  { label: "Created", key: "created" },
  {
    label: "",
    key: "actions",
    render: (row: Secret) => (
      <button className="p-1.5 rounded-lg text-[#6B7280] hover:bg-[#F4F7FA] hover:text-[#38B88A] transition-colors duration-150" title="Rotate">
        <RotateCcw className="w-4 h-4" />
      </button>
    ),
  },
]

// ─── COMPONENT ─────────────────────────────────────────────────────────────────

export default function SecretsPanel() {
  const [showAdd, setShowAdd] = useState(false)

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Secrets"
        subtitle="Manage API keys, tokens, and credentials"
        actions={
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-[18px] bg-[#38B88A] text-white text-sm font-medium hover:bg-[#2F9F77] transition-colors duration-150"
          >
            <Plus className="w-4 h-4" />
            Add Secret
          </button>
        }
      />

      {/* Expiry Warnings */}
      <div className="flex gap-3">
        {SECRETS.filter((s) => s.status === "expiring").length > 0 && (
          <div className="flex items-center gap-2 px-4 py-2 rounded-[18px] bg-[#FEF3C7] border border-[#F59E0B]/30">
            <AlertTriangle className="w-4 h-4 text-[#F59E0B]" />
            <span className="text-xs font-medium text-[#B45309]">{SECRETS.filter((s) => s.status === "expiring").length} secrets expiring soon</span>
          </div>
        )}
        {SECRETS.filter((s) => s.status === "expired").length > 0 && (
          <div className="flex items-center gap-2 px-4 py-2 rounded-[18px] bg-[#FEE2E2] border border-[#EF4444]/30">
            <AlertTriangle className="w-4 h-4 text-[#EF4444]" />
            <span className="text-xs font-medium text-[#B91C1C]">{SECRETS.filter((s) => s.status === "expired").length} secrets expired</span>
          </div>
        )}
      </div>

      <DataTable columns={columns} data={SECRETS} idKey="id" />

      {/* Add Secret Modal */}
      {showAdd && (
        <Modal title="Add Secret" onClose={() => setShowAdd(false)}>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-[#111827] block mb-1.5">Secret Name</label>
              <input type="text" placeholder="e.g. anthropic-api-key" className="w-full h-10 px-4 rounded-[18px] bg-[#F4F7FA] border border-[#E8EDF3] text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A]" />
            </div>
            <div>
              <label className="text-sm font-medium text-[#111827] block mb-1.5">Provider</label>
              <select className="w-full h-10 px-4 rounded-[18px] bg-[#F4F7FA] border border-[#E8EDF3] text-sm focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A]">
                <option>Vault</option>
                <option>Azure</option>
                <option>AWS</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-[#111827] block mb-1.5">Secret Value</label>
              <textarea rows={3} placeholder="Enter secret value..." className="w-full px-4 py-2 rounded-[18px] bg-[#F4F7FA] border border-[#E8EDF3] text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A] resize-none" />
            </div>
            <div>
              <label className="text-sm font-medium text-[#111827] block mb-1.5">Rotation Policy</label>
              <select className="w-full h-10 px-4 rounded-[18px] bg-[#F4F7FA] border border-[#E8EDF3] text-sm focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A]">
                <option>90 days</option>
                <option>180 days</option>
                <option>1 year</option>
                <option>Never</option>
              </select>
            </div>
          </div>
          <div className="flex items-center justify-end gap-3 mt-6">
            <button onClick={() => setShowAdd(false)} className="px-4 py-2 rounded-[18px] text-sm font-medium text-[#6B7280] hover:bg-[#F4F7FA] hover:text-[#111827] border border-[#E8EDF3] transition-colors">Cancel</button>
            <button onClick={() => setShowAdd(false)} className="flex items-center gap-2 px-4 py-2 rounded-[18px] bg-[#38B88A] text-white text-sm font-medium hover:bg-[#2F9F77] transition-colors">
              <Key className="w-4 h-4" />
              Add Secret
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}