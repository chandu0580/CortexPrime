"use client"

import { Activity } from "lucide-react"
import { DEFAULT_HEALTH_ITEMS } from "@/components/certification/definitions"
import { StatusIcon } from "@/components/certification/shared"
import { GlassCard } from "@/components/executive-platform/shared"

export default function HealthValidation() {
  const items = DEFAULT_HEALTH_ITEMS
  const healthy = items.filter((i) => i.status === "healthy").length

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Activity className="w-6 h-6 text-emerald-400" />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Health Validation</h1>
          <p className="text-xs text-white/40 mt-0.5">{healthy}/{items.length} subsystems healthy</p>
        </div>
      </div>
      <GlassCard>
        <div className="space-y-0">
          {items.map((item) => (
            <div key={item.name} className="flex items-center gap-3 px-3 py-2.5 border-b border-white/5 last:border-0">
              <StatusIcon status={item.status} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-white/80 font-medium">{item.name}</span>
                  <span className="text-xs text-white/30">{item.latency}</span>
                </div>
                <div className="flex items-center justify-between mt-0.5">
                  <span className="text-xs text-white/40">{item.detail}</span>
                  <span className="text-[10px] text-white/20">{item.lastChecked}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  )
}