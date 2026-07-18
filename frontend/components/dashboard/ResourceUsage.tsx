"use client"

import { Activity, Cpu, Database, DollarSign, MemoryStick, Sparkles, Terminal, BarChart3 } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Line, LineChart, ResponsiveContainer } from "recharts";
import { Card } from "./Card";
import { SectionHead } from "./SectionHeader";

const LABEL_ICONS: Record<string, LucideIcon> = {
  CPU: Cpu,
  Memory: MemoryStick,
  GPU: Sparkles,
  "Disk I/O": Terminal,
  "Token Usage": BarChart3,
  "Queue Len": Database,
  "Cost Today": DollarSign,
};

export function ResourceUsage({ items }: { items?: { label: string; value: string; color: string; data: number[] }[] }) {
  const isEmpty = !items || items.length === 0;
  return (
    <Card className="p-5">
      <SectionHead title="Resource Usage" action="View All" />
      <div className="space-y-3">
        {isEmpty && (
          <div className="flex flex-col items-center gap-2 py-6 text-center">
            <Activity className="h-8 w-8 text-[#D1D5DB]" />
            <p className="text-[0.86rem] font-medium text-[#9CA3AF]">No resource data</p>
            <p className="text-[0.75rem] text-[#B0B7C3]">Resource metrics will appear here when available</p>
          </div>
        )}
        {!isEmpty && items.map((r) => {
          const Icon = LABEL_ICONS[r.label] ?? Activity;
          return (
            <div key={r.label} className="flex items-center gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-[#F8FAFC]" style={{ color: r.color }}>
                <Icon className="h-4 w-4" />
              </div>
              <p className="w-16 shrink-0 text-[0.84rem] font-semibold text-[#374151]">{r.label}</p>
              <div className="h-8 flex-1">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={r.data.map((v, i) => ({ i, v }))} margin={{ top: 2, right: 2, bottom: 0, left: 2 }}>
                    <Line type="monotone" dataKey="v" stroke={r.color} strokeWidth={2} dot={false} isAnimationActive />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <span className="w-14 shrink-0 text-right text-[0.86rem] font-bold text-[#111827]">{r.value}</span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
