"use client"

import type { LucideIcon } from "lucide-react";
import { Cpu, MemoryStick, Sparkles, Terminal } from "lucide-react";
import { Line, LineChart, ResponsiveContainer } from "recharts";
import { cn } from "@/utils/cn";
import { Card } from "./Card";
import { SectionHead } from "./SectionHeader";

const RESOURCE_FALLBACKS = [
  { label: "CPU",      value: "32%", color: "#38B88A", icon: Cpu,         data: [18,22,21,29,27,32,30,35,32] },
  { label: "Memory",   value: "61%", color: "#3B82F6", icon: MemoryStick, data: [48,54,53,58,60,62,59,61,61] },
  { label: "GPU",      value: "24%", color: "#8B5CF6", icon: Sparkles,    data: [22,24,23,26,21,24,25,23,24] },
  { label: "Disk I/O", value: "18%", color: "#F59E0B", icon: Terminal,    data: [12,14,13,19,18,21,17,18,18] },
];

export function ResourceUsage({ items }: { items?: { label: string; value: string; color: string; data: number[] }[] }) {
  const list = items && items.length > 0 ? items : RESOURCE_FALLBACKS;
  const icons: LucideIcon[] = [Cpu, MemoryStick, Sparkles, Terminal];
  return (
    <Card className="p-5">
      <SectionHead title="Resource Usage" action="View All" />
      <div className="space-y-3">
        {list.map((r, idx) => {
          const Icon = icons[idx] ?? Cpu;
          return (
            <div key={r.label} className="flex items-center gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-[#F8FAFC]" style={{ color: r.color }}>
                <Icon className="h-4 w-4" />
              </div>
              <p className="w-14 shrink-0 text-[0.84rem] font-semibold text-[#374151]">{r.label}</p>
              <div className="h-8 flex-1">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={r.data.map((v, i) => ({ i, v }))} margin={{ top: 2, right: 2, bottom: 0, left: 2 }}>
                    <Line type="monotone" dataKey="v" stroke={r.color} strokeWidth={2} dot={false} isAnimationActive />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <span className="w-10 shrink-0 text-right text-[0.86rem] font-bold text-[#111827]">{r.value}</span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
