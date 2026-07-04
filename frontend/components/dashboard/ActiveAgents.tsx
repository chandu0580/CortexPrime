import type { LucideIcon } from "lucide-react";
import {
  Bot,
  Brain,
  ClipboardCheck,
  Database,
  Globe,
  Layers,
  Mic,
  Monitor,
  MoreVertical,
  Search,
  Zap,
} from "lucide-react";
import { cn } from "@/utils/cn";
import { Badge } from "./Badge";
import { Card } from "./Card";
import { SectionHead } from "./SectionHeader";
import type { StatusTone } from "@/components/dashboard/data";
import type { DashboardAgent } from "@/services/dashboard/agents";

const AGENT_ICONS: Record<string, LucideIcon> = {
  research: Search,
  memory: Database,
  orchestrator: Bot,
  planner: Layers,
  critic: ClipboardCheck,
  optimizer: Zap,
  reflection: Brain,
  browser: Globe,
  voice: Mic,
  computer: Monitor,
};

export function ActiveAgents({
  items,
  isLoading,
}: {
  items: DashboardAgent[];
  isLoading: boolean;
}) {
  const showSkeleton = isLoading && items.length === 0;
  const showEmpty = !isLoading && items.length === 0;

  return (
    <Card className="p-5">
      <SectionHead title="Active Agents" action="View All" />
      <div className="space-y-2.5">
        {showSkeleton && (
          <>
            {[1, 2, 3].map((n) => (
              <div key={n} className="flex animate-pulse items-center gap-3 rounded-[14px] border border-[#F0F4F8] bg-[#FAFCFE] px-3.5 py-3">
                <div className="h-9 w-9 shrink-0 rounded-[12px] bg-[#F0F4F8]" />
                <div className="min-w-0 flex-1 space-y-1.5">
                  <div className="h-3.5 w-3/4 rounded bg-[#F0F4F8]" />
                  <div className="h-3 w-1/2 rounded bg-[#F0F4F8]" />
                </div>
              </div>
            ))}
          </>
        )}
        {showEmpty && (
          <div className="flex flex-col items-center gap-2 py-6 text-center">
            <Bot className="h-8 w-8 text-[#D1D5DB]" />
            <p className="text-[0.86rem] font-medium text-[#9CA3AF]">No agents</p>
            <p className="text-[0.75rem] text-[#B0B7C3]">Agents will appear here when registered</p>
          </div>
        )}
        {!showSkeleton && !showEmpty && items.map((ag) => {
          const Icon = AGENT_ICONS[ag.name] ?? Bot;
          const isRunning = ag.status === "running";
          const isFailed = ag.status === "failed";
          const tone: StatusTone = isFailed ? "critical" : isRunning ? "running" : "idle";
          const secondary = ag.capabilities.length > 0
            ? ag.capabilities[0]
            : ag.agentType;
          const statusText = isFailed ? "Failed" : isRunning ? "Running" : "Idle";
          const meta = ag.tasksCompleted > 0
            ? `${ag.tasksCompleted} tasks`
            : isRunning ? "Active" : "Standing by";

          return (
            <div key={ag.name} className="flex items-center gap-3 rounded-[14px] border border-[#F0F4F8] bg-[#FAFCFE] px-3.5 py-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[12px] bg-[#ECFBF4] text-[#38B88A]">
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[0.86rem] font-semibold text-[#111827]">{ag.displayName}</p>
                <p className="truncate text-[0.74rem] text-[#9CA3AF]">{secondary}</p>
              </div>
              <div className="shrink-0 text-right">
                <Badge tone={tone}>{statusText}</Badge>
                <p className="mt-1 text-[0.72rem] text-[#9CA3AF]">{meta}</p>
              </div>
              <MoreVertical className="h-4 w-4 shrink-0 text-[#D1D5DB]" />
            </div>
          );
        })}
      </div>
    </Card>
  );
}
