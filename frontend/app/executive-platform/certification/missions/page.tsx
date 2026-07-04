"use client"

import { Crosshair } from "lucide-react"
import { DEFAULT_MISSION_CERTIFICATIONS } from "@/components/certification/definitions"
import { CertificationBadge } from "@/components/certification/shared"
import { GlassCard } from "@/components/executive-platform/shared"
import { CheckCircle2, FileText, History, Shield } from "lucide-react"

export default function MissionCertification() {
  const missions = DEFAULT_MISSION_CERTIFICATIONS
  const certified = missions.filter((m) => m.status === "certified").length

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Crosshair className="w-6 h-6 text-emerald-400" />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Mission Certification</h1>
          <p className="text-xs text-white/40 mt-0.5">{certified}/{missions.length} missions certified</p>
        </div>
      </div>
      <GlassCard>
        <div className="space-y-1">
          {missions.map((m) => (
            <div key={m.missionId} className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/[0.02]">
              <div className={`w-2 h-2 rounded-full ${m.status === "certified" ? "bg-emerald-400" : m.status === "failed" ? "bg-red-400" : "bg-amber-400"}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-white/80 font-medium">{m.name}</span>
                  <CertificationBadge status={m.status} />
                </div>
                <div className="flex items-center gap-3 mt-0.5 text-[10px] text-white/30">
                  {m.status === "certified" && <><span>Duration: {m.duration}</span><span>Stages: {m.stagesPassed}/{m.stagesTotal}</span></>}
                  <div className="flex items-center gap-1.5 ml-auto">
                    {m.hasReplay && <CheckCircle2 className="w-3 h-3 text-emerald-400/60" />}
                    {m.hasReport && <FileText className="w-3 h-3 text-blue-400/60" />}
                    {m.hasAudit && <Shield className="w-3 h-3 text-violet-400/60" />}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  )
}