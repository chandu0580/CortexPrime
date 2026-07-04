"use client"

import { BarChart3 } from "lucide-react"
import { DEFAULT_BENCHMARKS } from "@/components/certification/definitions"
import { StatusIcon } from "@/components/certification/shared"
import { GlassCard } from "@/components/executive-platform/shared"

export default function PerformanceBenchmarks() {
  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <BarChart3 className="w-6 h-6 text-emerald-400" />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Performance Benchmarks</h1>
          <p className="text-xs text-white/40 mt-0.5">Latency measurements across all subsystems</p>
        </div>
      </div>
      <GlassCard>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/5">
                <th className="text-left text-[10px] text-white/30 font-medium uppercase py-2 px-3">Benchmark</th>
                <th className="text-right text-[10px] text-white/30 font-medium uppercase py-2 px-3">Value</th>
                <th className="text-right text-[10px] text-white/30 font-medium uppercase py-2 px-3">p50</th>
                <th className="text-right text-[10px] text-white/30 font-medium uppercase py-2 px-3">p95</th>
                <th className="text-right text-[10px] text-white/30 font-medium uppercase py-2 px-3">p99</th>
                <th className="text-right text-[10px] text-white/30 font-medium uppercase py-2 px-3">Samples</th>
                <th className="text-right text-[10px] text-white/30 font-medium uppercase py-2 px-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {DEFAULT_BENCHMARKS.map((b) => (
                <tr key={b.name} className="border-b border-white/5 hover:bg-white/[0.02]">
                  <td className="py-2.5 px-3 text-white/70">{b.name}</td>
                  <td className="py-2.5 px-3 text-right text-white/80 font-mono">{b.value}</td>
                  <td className="py-2.5 px-3 text-right text-white/50 font-mono">{b.p50}</td>
                  <td className="py-2.5 px-3 text-right text-white/50 font-mono">{b.p95}</td>
                  <td className="py-2.5 px-3 text-right text-white/50 font-mono">{b.p99}</td>
                  <td className="py-2.5 px-3 text-right text-white/40">{b.samples}</td>
                  <td className="py-2.5 px-3 text-right"><StatusIcon status={b.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>
    </div>
  )
}