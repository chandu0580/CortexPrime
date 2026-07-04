"use client"

import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { AnimatedNum } from "./AnimatedNumber";
import { Card } from "./Card";
import type { KpiMetric } from "@/components/dashboard/data";

export function KpiCard({ metric }: { metric: KpiMetric }) {
  const isSystemHealth = metric.label === "System Health";
  const data = metric.data.map((v, i) => ({ i, v }));
  return (
    <Card className="px-5 py-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[0.8rem] font-medium text-[#6B7280]">{metric.label}</p>
          <p className="mt-2 text-[2rem] font-bold leading-none tracking-[-0.04em] text-[#111827]">
            {isSystemHealth ? (
              <span className="text-[1.5rem]">Excellent</span>
            ) : (
              <AnimatedNum value={metric.value} />
            )}
          </p>
          {isSystemHealth && (
            <p className="mt-0.5 text-[0.76rem] text-[#9CA3AF]">All systems operational</p>
          )}
        </div>
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[14px] bg-[#ECFBF4] text-[#38B88A]">
          <metric.icon className="h-5 w-5" />
        </div>
      </div>
      {!isSystemHealth && (
        <div className="mt-3 flex items-end justify-between gap-2">
          <div>
            <p className="text-[0.8rem]">
              <span className="font-semibold text-[#38B88A]">{metric.trend.split(" ")[0]}</span>{" "}
              <span className="text-[#9CA3AF]">{metric.trend.split(" ").slice(1).join(" ")}</span>
            </p>
          </div>
          <div className="h-8 w-20" aria-hidden>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data} margin={{ top: 2, right: 2, bottom: 0, left: 2 }}>
                <Area type="monotone" dataKey="v" stroke="#38B88A" strokeWidth={1.8} fill="#38B88A" fillOpacity={0.1} dot={false} isAnimationActive />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </Card>
  );
}
