"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import {
  Brain,
  Activity,
  AlertTriangle,
  CheckCircle,
  BarChart3,
  DollarSign,
  Gauge,
  Server,
  Clock,
} from "lucide-react"

import { cn } from "@/utils/cn"
import { StatusBadge, KpiCard, SectionHeader } from "./shared"

// ─── TYPES ─────────────────────────────────────────────────────────────────────

interface Model {
  id: string
  name: string
  status: "healthy" | "degraded"
  latency: string
  rateLimit: string
}

interface Provider {
  id: string
  name: string
  icon: typeof Brain
  color: string
  status: "healthy" | "degraded"
  overallLatency: string
  models: Model[]
}

interface CostPolicy {
  model: string
  inputPrice: string
  outputPrice: string
  rateLimit: string
  fallback: string
}

interface UsageData {
  month: string
  tokens: number
  cost: number
}

// ─── MOCK DATA ─────────────────────────────────────────────────────────────────

const PROVIDERS: Provider[] = [
  {
    id: "openai", name: "OpenAI", icon: Brain, color: "#10A37F", status: "healthy", overallLatency: "245ms",
    models: [
      { id: "gpt-4o", name: "GPT-4o", status: "healthy", latency: "320ms", rateLimit: "10k/min" },
      { id: "gpt-4o-mini", name: "GPT-4o Mini", status: "healthy", latency: "180ms", rateLimit: "30k/min" },
      { id: "o1", name: "O1", status: "healthy", latency: "2.1s", rateLimit: "100/min" },
    ],
  },
  {
    id: "anthropic", name: "Anthropic", icon: Brain, color: "#5436DA", status: "healthy", overallLatency: "410ms",
    models: [
      { id: "claude-opus", name: "Claude Opus", status: "healthy", latency: "520ms", rateLimit: "5k/min" },
      { id: "claude-sonnet", name: "Claude Sonnet", status: "healthy", latency: "280ms", rateLimit: "15k/min" },
    ],
  },
  {
    id: "google", name: "Google", icon: Brain, color: "#4285F4", status: "degraded", overallLatency: "890ms",
    models: [
      { id: "gemini-pro", name: "Gemini Pro", status: "degraded", latency: "950ms", rateLimit: "8k/min" },
    ],
  },
  {
    id: "azure", name: "Azure OpenAI", icon: Server, color: "#0078D4", status: "healthy", overallLatency: "310ms",
    models: [
      { id: "azure-gpt-4", name: "GPT-4 (Azure)", status: "healthy", latency: "340ms", rateLimit: "10k/min" },
      { id: "azure-gpt-35", name: "GPT-3.5 (Azure)", status: "healthy", latency: "190ms", rateLimit: "20k/min" },
    ],
  },
]

const COST_POLICIES: CostPolicy[] = [
  { model: "GPT-4o", inputPrice: "$2.50/M", outputPrice: "$10.00/M", rateLimit: "10k/min", fallback: "GPT-4o Mini" },
  { model: "GPT-4o Mini", inputPrice: "$0.15/M", outputPrice: "$0.60/M", rateLimit: "30k/min", fallback: "-" },
  { model: "Claude Opus", inputPrice: "$15.00/M", outputPrice: "$75.00/M", rateLimit: "5k/min", fallback: "Claude Sonnet" },
  { model: "Claude Sonnet", inputPrice: "$3.00/M", outputPrice: "$15.00/M", rateLimit: "15k/min", fallback: "-" },
  { model: "Gemini Pro", inputPrice: "$1.00/M", outputPrice: "$4.00/M", rateLimit: "8k/min", fallback: "-" },
  { model: "GPT-4 (Azure)", inputPrice: "$2.50/M", outputPrice: "$10.00/M", rateLimit: "10k/min", fallback: "GPT-3.5 (Azure)" },
]

const USAGE_DATA: UsageData[] = [
  { month: "Jan", tokens: 2.4, cost: 185 },
  { month: "Feb", tokens: 3.1, cost: 242 },
  { month: "Mar", tokens: 4.8, cost: 389 },
  { month: "Apr", tokens: 5.2, cost: 415 },
  { month: "May", tokens: 6.7, cost: 528 },
  { month: "Jun", tokens: 7.9, cost: 634 },
]

const MAX_TOKENS = Math.max(...USAGE_DATA.map((u) => u.tokens))
const MAX_COST = Math.max(...USAGE_DATA.map((u) => u.cost))

// ─── COMPONENT ─────────────────────────────────────────────────────────────────

export default function ModelsPanel() {
  return (
    <div className="space-y-6">
      <SectionHeader title="AI Models" subtitle="Manage provider configurations and model usage" />

      {/* Provider Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {PROVIDERS.map((provider) => {
          const Icon = provider.icon
          return (
            <div key={provider.id} className="border border-[#E8EDF3] bg-white rounded-[18px] p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: `${provider.color}15` }}>
                    <Icon className="w-5 h-5" style={{ color: provider.color }} />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-[#111827]">{provider.name}</h3>
                    <div className="flex items-center gap-2 text-xs text-[#6B7280] mt-0.5">
                      <span>{provider.overallLatency}</span>
                      <span className="w-1 h-1 rounded-full bg-[#D1D5DB]" />
                      <StatusBadge tone={provider.status} label={provider.status} />
                    </div>
                  </div>
                </div>
                <div className={cn("w-2 h-2 rounded-full", provider.status === "healthy" ? "bg-[#38B88A]" : "bg-[#F59E0B]")} />
              </div>
              <div className="space-y-2">
                {provider.models.map((model) => (
                  <div key={model.id} className="flex items-center justify-between px-3 py-2 rounded-xl bg-[#F4F7FA]">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-[#111827]">{model.name}</span>
                      {model.status === "degraded" && <AlertTriangle className="w-3.5 h-3.5 text-[#F59E0B]" />}
                    </div>
                    <div className="flex items-center gap-3 text-xs text-[#6B7280]">
                      <span>{model.latency}</span>
                      <span>{model.rateLimit}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {/* Cost Policy Table */}
      <div>
        <SectionHeader title="Cost Policy" subtitle="Pricing, rate limits, and fallback strategies" />
        <div className="border border-[#E8EDF3] bg-white rounded-[18px] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E8EDF3] bg-[#F4F7FA]">
                {["Model", "Input Price", "Output Price", "Rate Limit", "Fallback"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-[#6B7280] uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {COST_POLICIES.map((policy, i) => (
                <tr key={i} className="border-b border-[#E8EDF3] last:border-0 hover:bg-[#F4F7FA] transition-colors">
                  <td className="px-4 py-3 font-medium text-[#111827]">{policy.model}</td>
                  <td className="px-4 py-3 text-[#111827]">{policy.inputPrice}</td>
                  <td className="px-4 py-3 text-[#111827]">{policy.outputPrice}</td>
                  <td className="px-4 py-3 text-[#111827]">{policy.rateLimit}</td>
                  <td className="px-4 py-3 text-[#6B7280]">{policy.fallback}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Usage Bar Chart */}
      <div>
        <SectionHeader title="Monthly Usage" subtitle="Token consumption and cost trends" />
        <div className="border border-[#E8EDF3] bg-white rounded-[18px] p-5">
          <div className="flex gap-6">
            <div className="flex-1">
              <p className="text-xs font-semibold text-[#6B7280] uppercase tracking-wider mb-3">Tokens (millions)</p>
              <div className="flex items-end gap-2 h-32">
                {USAGE_DATA.map((d) => (
                  <div key={d.month} className="flex-1 flex flex-col items-center gap-1">
                    <motion.div
                      className="w-full rounded-t-md"
                      style={{ backgroundColor: "#38B88A", opacity: 0.3 + (d.tokens / MAX_TOKENS) * 0.7 }}
                      initial={{ height: 0 }}
                      animate={{ height: `${(d.tokens / MAX_TOKENS) * 100}%` }}
                      transition={{ duration: 0.5, ease: "easeOut" }}
                    />
                    <span className="text-[10px] text-[#6B7280]">{d.month}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="w-px bg-[#E8EDF3]" />
            <div className="flex-1">
              <p className="text-xs font-semibold text-[#6B7280] uppercase tracking-wider mb-3">Cost (USD)</p>
              <div className="flex items-end gap-2 h-32">
                {USAGE_DATA.map((d) => (
                  <div key={d.month} className="flex-1 flex flex-col items-center gap-1">
                    <motion.div
                      className="w-full rounded-t-md"
                      style={{ backgroundColor: "#F59E0B", opacity: 0.3 + (d.cost / MAX_COST) * 0.7 }}
                      initial={{ height: 0 }}
                      animate={{ height: `${(d.cost / MAX_COST) * 100}%` }}
                      transition={{ duration: 0.5, ease: "easeOut" }}
                    />
                    <span className="text-[10px] text-[#6B7280]">{d.month}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}