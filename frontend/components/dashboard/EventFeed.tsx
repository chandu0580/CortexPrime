"use client"

import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Bot,
  Globe,
  Layers,
  Mic,
  Monitor,
  Search,
  Shield,
  Target,
  Zap,
} from "lucide-react";
import { cn } from "@/utils/cn";
import { toneStyles } from "./Badge";
import { Card } from "./Card";
import { SectionHead } from "./SectionHeader";
import type { StatusTone } from "@/components/dashboard/data";
import type { DashboardEvent } from "@/services/dashboard/events";

const EVENT_ICONS: Record<string, LucideIcon> = {
  mission: Target,
  runtime: Zap,
  agent: Bot,
  voice: Mic,
  browser: Globe,
  computer: Monitor,
  research: Search,
  governance: Shield,
  system: Layers,
};

const SEVERITY_TONE: Record<string, StatusTone> = {
  success: "completed",
  error: "critical",
  warning: "warning",
  info: "info",
};

function relativeTime(date: Date): string {
  const s = Math.floor((Date.now() - date.getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

export function EventFeed({
  items,
  isLoading,
}: {
  items: DashboardEvent[];
  isLoading: boolean;
}) {
  const showSkeleton = isLoading && items.length === 0;
  const showEmpty = !isLoading && items.length === 0;

  return (
    <Card className="p-5">
      <SectionHead title="Recent Activity" action="View All" />
      <div className="space-y-3">
        {showSkeleton && (
          <>
            {[1, 2, 3].map((n) => (
              <div key={n} className="flex animate-pulse items-center gap-3">
                <div className="h-8 w-8 shrink-0 rounded-[10px] bg-[#F0F4F8]" />
                <div className="flex-1 space-y-1.5">
                  <div className="h-3 w-5/6 rounded bg-[#F0F4F8]" />
                  <div className="h-3 w-1/3 rounded bg-[#F0F4F8]" />
                </div>
              </div>
            ))}
          </>
        )}
        {showEmpty && (
          <div className="flex flex-col items-center gap-2 py-6 text-center">
            <Activity className="h-8 w-8 text-[#D1D5DB]" />
            <p className="text-[0.86rem] font-medium text-[#9CA3AF]">No recent activity</p>
            <p className="text-[0.75rem] text-[#B0B7C3]">Events will appear here as they occur</p>
          </div>
        )}
        {!showSkeleton && !showEmpty && items.map((ev) => {
          const Icon = EVENT_ICONS[ev.type] ?? Activity;
          const tone = SEVERITY_TONE[ev.severity] ?? "info";
          return (
            <div key={ev.id} className="flex items-center gap-3">
              <div className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px]", toneStyles[tone])}>
                <Icon className="h-4 w-4" />
              </div>
              <p className="flex-1 text-[0.81rem] leading-[1.4] text-[#374151]">{ev.description || ev.title}</p>
              <span className="shrink-0 text-[0.73rem] text-[#9CA3AF]">{relativeTime(ev.timestamp)}</span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
