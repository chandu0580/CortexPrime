"use client"

import { PolarAngleAxis, RadialBar, RadialBarChart, ResponsiveContainer } from "recharts";
import { Card } from "./Card";
import { SectionHead } from "./SectionHeader";

const STATUS_COLORS: Record<string, { dot: string; text: string }> = {
  healthy:     { dot: "#38B88A", text: "#38B88A" },
  warning:     { dot: "#F59E0B", text: "#B45309" },
  unavailable: { dot: "#EF4444", text: "#B91C1C" },
  unknown:     { dot: "#9CA3AF", text: "#9CA3AF" },
};
const STATUS_LABELS: Record<string, string> = {
  healthy:     "Healthy",
  warning:     "Warning",
  unavailable: "Offline",
  unknown:     "Unknown",
};

export function SystemHealthPanel({ overallHealth = 98.7, services = [] }: {
  overallHealth?: number;
  services?: { label: string; status: string }[];
}) {
  const chartData = [{ name: "Health", value: overallHealth, fill: "#38B88A" }];
  return (
    <Card className="p-5">
      <SectionHead title="System Health" action="View All" />
      <div className="flex gap-5">
        <div className="relative flex h-[110px] w-[110px] shrink-0 items-center justify-center">
          <ResponsiveContainer width="100%" height="100%">
            <RadialBarChart innerRadius="72%" outerRadius="100%" data={chartData} startAngle={90} endAngle={-270}>
              <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
              <RadialBar dataKey="value" cornerRadius={8} background={{ fill: "#F0F4F8" }} isAnimationActive />
            </RadialBarChart>
          </ResponsiveContainer>
          <div className="absolute text-center">
            <p className="text-[1rem] font-bold leading-tight text-[#111827]">{overallHealth}%</p>
            <p className="text-[0.62rem] text-[#9CA3AF]">Overall Health</p>
          </div>
        </div>
        <div className="flex-1 space-y-1.5 self-center">
          {(services.length > 0 ? services : [
            { label: "API Services",  status: "healthy" },
            { label: "Database",      status: "healthy" },
            { label: "Vector Store",  status: "healthy" },
            { label: "Redis Cache",   status: "healthy" },
            { label: "Message Queue", status: "healthy" },
            { label: "Voice Services",status: "healthy" },
          ]).map((s) => {
            const colors = STATUS_COLORS[s.status] ?? STATUS_COLORS.unknown;
            return (
              <div key={s.label} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: colors.dot }} />
                  <span className="text-[0.79rem] text-[#374151]">{s.label}</span>
                </div>
                <span className="text-[0.76rem] font-semibold" style={{ color: colors.text }}>
                  {STATUS_LABELS[s.status] ?? "Unknown"}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
}
