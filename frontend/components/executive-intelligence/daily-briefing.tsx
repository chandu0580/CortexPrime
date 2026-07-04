"use client"

import { useEffect, useState } from "react"
import { Sun, AlertTriangle, TrendingUp, DollarSign, Shield } from "lucide-react"
import { useIntelligenceStore } from "@/store/intelligenceStore"
import { GlassCard, PulseDot } from "@/components/executive-platform/shared"
import type { BriefingSection, Recommendation } from "@/services/intelligence/executiveIntelligence"

export function DailyBriefing() {
  const { snapshot, loadSnapshot } = useIntelligenceStore()
  const [greeting, setGreeting] = useState("")

  useEffect(() => {
    const hour = new Date().getHours()
    if (hour < 12) setGreeting("Good morning")
    else if (hour < 18) setGreeting("Good afternoon")
    else setGreeting("Good evening")
    loadSnapshot()
    const interval = setInterval(loadSnapshot, 60000)
    return () => clearInterval(interval)
  }, [loadSnapshot])

  const sections = snapshot?.briefing || []
  const recommendations = snapshot?.recommendations || []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Sun className="w-5 h-5 text-amber-400" />
          <div>
            <h2 className="text-base font-semibold">{greeting}, Executive</h2>
            <p className="text-xs text-white/40">CortexPrime Intelligence Briefing · {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}</p>
          </div>
        </div>
        <PulseDot />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {sections.filter((s) => s.priority === "critical" || s.priority === "high").map((section) => (
          <GlassCard key={section.title}>
            <div className="flex items-center gap-2 mb-2">
              {section.priority === "critical" && <AlertTriangle className="w-3.5 h-3.5 text-red-400" />}
              <h3 className="text-xs font-medium text-white/60 uppercase tracking-wider">{section.title}</h3>
            </div>
            <div className="space-y-1.5">
              {section.items.map((item) => (
                <div key={item.label} className="flex items-center justify-between text-sm">
                  <span className="text-white/50">{item.label}</span>
                  <div className="flex items-center gap-2">
                    <span className={item.status === "warning" ? "text-amber-400" : item.status === "critical" ? "text-red-400" : "text-white/80"}>{item.value}</span>
                    {item.action && <span className="text-[10px] text-emerald-400 cursor-pointer hover:underline">{item.action}</span>}
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {sections.filter((s) => s.priority === "normal" || s.priority === "low").map((section) => (
          <GlassCard key={section.title}>
            <h3 className="text-xs font-medium text-white/40 uppercase tracking-wider mb-2">{section.title}</h3>
            <div className="space-y-1.5">
              {section.items.map((item) => (
                <div key={item.label} className="flex items-center justify-between text-sm">
                  <span className="text-white/40">{item.label}</span>
                  <span className="text-white/60">{item.value}</span>
                </div>
              ))}
            </div>
          </GlassCard>
        ))}
      </div>

      {recommendations.length > 0 && (
        <GlassCard>
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
            <h3 className="text-xs font-medium text-white/60 uppercase tracking-wider">Recommendations</h3>
          </div>
          <div className="space-y-2">
            {recommendations.map((rec) => (
              <div key={rec.id} className="flex items-start gap-2 p-2 rounded-lg hover:bg-white/[0.02]">
                {rec.type === "risk" && <AlertTriangle className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />}
                {rec.type === "cost" && <DollarSign className="w-3.5 h-3.5 text-violet-400 mt-0.5 shrink-0" />}
                {rec.type === "security" && <Shield className="w-3.5 h-3.5 text-red-400 mt-0.5 shrink-0" />}
                {rec.type === "mission" && <TrendingUp className="w-3.5 h-3.5 text-blue-400 mt-0.5 shrink-0" />}
                <div>
                  <div className="text-sm text-white/70">{rec.title}</div>
                  <div className="text-xs text-white/30 mt-0.5">{rec.action}</div>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      )}
    </div>
  )
}