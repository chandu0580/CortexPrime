"use client"

import { Lock } from "lucide-react"
import { DEFAULT_SECURITY_ITEMS } from "@/components/certification/definitions"
import { StatusIcon } from "@/components/certification/shared"
import { GlassCard, StatusBadge } from "@/components/executive-platform/shared"

export default function SecurityValidation() {
  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Lock className="w-6 h-6 text-emerald-400" />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Security Validation</h1>
          <p className="text-xs text-white/40 mt-0.5">Security controls and access management verification</p>
        </div>
      </div>
      <GlassCard>
        <div className="space-y-0">
          {DEFAULT_SECURITY_ITEMS.map((item) => (
            <div key={item.name} className="flex items-center gap-3 px-3 py-2.5 border-b border-white/5 last:border-0">
              <StatusIcon status={item.status} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-white/80 font-medium">{item.name}</span>
                  <StatusBadge status={item.severity} label={item.severity} />
                </div>
                <p className="text-xs text-white/40 mt-0.5">{item.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  )
}