import { Target } from "lucide-react";
import { cn } from "@/utils/cn";
import { Badge } from "./Badge";
import { Card } from "./Card";
import { SectionHead } from "./SectionHeader";
import type { StatusTone } from "@/components/dashboard/data";
import type { DashboardTimelineItem } from "@/services/dashboard/timeline";

function formatTime(date: Date | null): string {
  if (!date) return "\u2014";
  return date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function MissionTimeline({
  items,
  tlPoints,
  isLoading,
}: {
  items: DashboardTimelineItem[];
  tlPoints: { x: number; y: number }[];
  isLoading: boolean;
}) {
  const showSkeleton = isLoading && items.length === 0;
  const showEmpty = !isLoading && items.length === 0;

  return (
    <Card className="p-5">
      <SectionHead title="Mission Timeline" action={<Badge tone="running">Live</Badge>} />
      <div className="flex gap-4">
        <div className="flex-1 space-y-3">
          {showSkeleton && (
            <>
              {[1, 2, 3].map((n) => (
                <div key={n} className="flex animate-pulse items-center gap-3">
                  <div className="h-8 w-8 shrink-0 rounded-[10px] bg-[#F0F4F8]" />
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
              <Target className="h-8 w-8 text-[#D1D5DB]" />
              <p className="text-[0.86rem] font-medium text-[#9CA3AF]">No missions</p>
              <p className="text-[0.75rem] text-[#B0B7C3]">Missions will appear here when started</p>
            </div>
          )}
          {!showSkeleton && !showEmpty && items.map((m) => {
            const isRunning = m.status === "running";
            const isCompleted = m.status === "completed";
            const isFailed = m.status === "failed";
            const isQueued = m.status === "queued";

            const tone: StatusTone = isCompleted
              ? "completed"
              : isFailed
              ? "critical"
              : isRunning
              ? "running"
              : "idle";

            return (
              <div key={m.id} className="flex items-center gap-3">
                <div className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] text-xs font-bold",
                  isCompleted ? "bg-[#ECFBF4] text-[#38B88A]"
                    : isFailed ? "bg-[#FEF2F2] text-[#EF4444]"
                    : isQueued ? "bg-[#F8FAFC] text-[#9CA3AF]"
                    : "bg-[#EFF6FF] text-[#3B82F6]",
                )}>
                  {isCompleted ? "\u2713"
                    : isFailed ? "!"
                    : <Target className="h-3.5 w-3.5" />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="truncate text-[0.87rem] font-semibold text-[#111827]">
                      {m.name}
                    </p>
                    {m.assignedAgent && (
                      <span className="shrink-0 truncate text-[0.7rem] text-[#9CA3AF]">
                        {m.assignedAgent}
                      </span>
                    )}
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <div className="flex h-1.5 flex-1 overflow-hidden rounded-full bg-[#F0F4F8]">
                      <div
                        className={cn(
                          "h-full rounded-full transition-all",
                          isCompleted ? "bg-[#38B88A]"
                            : isFailed ? "bg-[#EF4444]"
                            : "bg-[#3B82F6]",
                        )}
                        style={{ width: `${m.progress ?? 0}%` }}
                      />
                    </div>
                    <span className="shrink-0 text-[0.7rem] font-medium text-[#6B7280] min-w-[2.5rem] text-right">
                      {m.progress != null ? `${m.progress}%` : "\u2014"}
                    </span>
                    {m.startedAt && (
                      <span className="hidden shrink-0 text-[0.7rem] text-[#9CA3AF] sm:block">
                        {formatTime(m.startedAt)}
                      </span>
                    )}
                    {m.duration && (
                      <span className="hidden shrink-0 text-[0.7rem] font-medium text-[#6B7280] md:block">
                        {m.duration}
                      </span>
                    )}
                  </div>
                </div>
                <Badge tone={tone}>
                  {isCompleted ? "Completed"
                    : isFailed ? "Failed"
                    : isQueued ? "Queued"
                    : "Running"}
                </Badge>
              </div>
            );
          })}
        </div>

        {items.length > 0 && (
          <div className="hidden w-[155px] shrink-0 flex-col md:flex">
            <svg viewBox="0 0 260 180" className="w-full flex-1" preserveAspectRatio="none">
              <defs>
                <linearGradient id="tlg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38B88A" stopOpacity="0.18" />
                  <stop offset="100%" stopColor="#38B88A" stopOpacity="0" />
                </linearGradient>
              </defs>
              {[45, 90, 135].map((y) => (
                <line key={y} x1="30" y1={y} x2="240" y2={y} stroke="#F0F4F8" strokeWidth="1" />
              ))}
              <path
                d={`M ${tlPoints.map((p) => `${p.x},${p.y}`).join(" L ")} L ${tlPoints[tlPoints.length - 1].x},180 L ${tlPoints[0].x},180 Z`}
                fill="url(#tlg)"
              />
              <polyline
                points={tlPoints.map((p) => `${p.x},${p.y}`).join(" ")}
                fill="none" stroke="#38B88A" strokeWidth="2.5"
                strokeLinejoin="round" strokeLinecap="round"
              />
              {tlPoints.map((p, i) => (
                <g key={i}>
                  <circle cx={p.x} cy={p.y} r="5" fill="white" stroke="#38B88A" strokeWidth="2.5" />
                  {i === tlPoints.length - 1 && (
                    <circle cx={p.x} cy={p.y} r="9" fill="none" stroke="#38B88A" strokeWidth="1.5" strokeOpacity="0.3" />
                  )}
                </g>
              ))}
            </svg>
            <button className="mt-3 w-full rounded-[10px] border border-[#EAEFF5] py-1.5 text-[0.76rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC] transition">
              View Full Timeline
            </button>
          </div>
        )}
      </div>
    </Card>
  );
}
