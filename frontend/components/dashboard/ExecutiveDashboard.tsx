"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Bot, ClipboardCheck, Plus, ShieldCheck, Sparkles, Target } from "lucide-react";

import { cn } from "@/utils/cn";
import { stagger, variants } from "@/lib/motion-tokens";
import type { StatusTone } from "@/components/dashboard/data";
import { useDashboardOverview, useDashboardHealth, useDashboardResources, useDashboardTimeline, useDashboardAgents, useDashboardEvents, useDashboardHeader, useDashboardWebSocket } from "@/hooks";

import { Sidebar } from "./Sidebar";
import { ExecutiveHeader } from "./ExecutiveHeader";
import { KpiCard } from "./KpiCard";
import { MissionTimeline } from "./MissionTimeline";
import { ActiveAgents } from "./ActiveAgents";
import { SystemHealthPanel } from "./SystemHealthPanel";
import { EventFeed } from "./EventFeed";
import { ResourceUsage } from "./ResourceUsage";

export default function ExecutiveDashboard() {
  const [collapsed, setCollapsed] = useState(false);
  const { data: overview } = useDashboardOverview();
  const { data: health } = useDashboardHealth();
  const { data: resources } = useDashboardResources();
  const { data: timeline, isLoading: isTimelineLoading } = useDashboardTimeline();
  const { data: agents, isLoading: isAgentsLoading } = useDashboardAgents();
  const { data: events, isLoading: isEventsLoading } = useDashboardEvents();
  const { data: header } = useDashboardHeader();

  useDashboardWebSocket();

  const displayMetrics = useMemo(() => {
    if (!overview) return [];

    const metrics = [
      {
        label: "Active Agents",
        value: String(overview.activeAgents),
        trend: overview.agentTrend,
        status: "Live",
        tone: "running" as StatusTone,
        icon: Bot,
        data: overview.agentsSparkline,
      },
      {
        label: "Running Missions",
        value: String(overview.runningMissions),
        trend: overview.missionTrend,
        status: "Running",
        tone: "running" as StatusTone,
        icon: Target,
        data: overview.missionsSparkline,
      },
      {
        label: "System Health",
        value: overview.systemHealth,
        trend: overview.healthTrend,
        status: overview.systemHealth === "Excellent" ? "Healthy" : overview.systemHealth,
        tone: (overview.systemHealth === "Excellent" ? "healthy" : "warning") as StatusTone,
        icon: ShieldCheck,
        data: overview.healthSparkline,
      },
      {
        label: "Success Rate",
        value: overview.successRate != null ? `${overview.successRate}%` : "\u2014",
        trend: overview.rateTrend,
        status: "Stable",
        tone: (overview.successRate != null && overview.successRate >= 95 ? "healthy" : "info") as StatusTone,
        icon: ClipboardCheck,
        data: overview.rateSparkline,
      },
    ];

    return metrics;
  }, [overview]);

  return (
    <div className="min-h-screen bg-[#F4F7FA] text-[#111827]">
      <Sidebar collapsed={collapsed} onCollapse={() => setCollapsed((v) => !v)} />

      <div className={cn("flex min-h-screen flex-col transition-all duration-300", collapsed ? "pl-[68px]" : "pl-[220px]")}>
        <ExecutiveHeader collapsed={collapsed} data={header?.header} />

        <main className="flex-1 px-5 py-5 lg:px-6">
          <motion.div
            initial="hidden"
            animate="visible"
            variants={stagger(0.04, 0.02)}
            className="mx-auto max-w-[1500px] space-y-5"
          >
            {/* Greeting */}
            <motion.div variants={variants.fadeUp} className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-[1.55rem] font-bold tracking-[-0.03em] text-[#111827]">
                  Good morning, Alex 👋
                </h1>
                <p className="mt-1 text-[0.88rem] text-[#6B7280]">
                  Here&apos;s what&apos;s happening with your AI workforce today.
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2.5">
                <button className="flex items-center gap-2 rounded-[14px] bg-[#38B88A] px-4 py-2.5 text-[0.86rem] font-semibold text-white shadow-[0_4px_12px_rgba(56,184,138,0.28)] transition hover:bg-[#2F9F77]">
                  <Plus className="h-4 w-4" /> New Mission
                </button>
                <button className="flex items-center gap-2 rounded-[14px] border border-[#EAEFF5] bg-white px-4 py-2.5 text-[0.86rem] font-semibold text-[#374151] transition hover:bg-[#F8FAFC]">
                  <Sparkles className="h-4 w-4 text-[#38B88A]" /> Ask Cortex
                </button>
              </div>
            </motion.div>

            {/* KPIs */}
            <motion.div variants={stagger(0.05)} className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {displayMetrics.map((m) => <KpiCard key={m.label} metric={m} />)}
            </motion.div>

            {/* Mission Timeline + Active Agents */}
            <motion.div variants={stagger(0.05)} className="grid gap-5 lg:grid-cols-[1fr_340px]">
              <MissionTimeline items={timeline?.items ?? []} tlPoints={timeline?.tlPoints ?? []} isLoading={isTimelineLoading} />
              <ActiveAgents items={agents?.items ?? []} isLoading={isAgentsLoading} />
            </motion.div>

            {/* System Health + Recent Activity + Resource Usage */}
            <motion.div variants={stagger(0.05)} className="grid gap-5 lg:grid-cols-3">
              <SystemHealthPanel overallHealth={health?.overallHealth} services={health?.services} />
              <EventFeed items={events?.items ?? []} isLoading={isEventsLoading} />
              <ResourceUsage items={resources?.resources} />
            </motion.div>

            {/* Footer */}
            <motion.footer
              variants={variants.fadeUp}
              className="flex flex-col gap-2 border-t border-[#EAEFF5] pt-5 pb-2 text-[0.78rem] text-[#9CA3AF] md:flex-row md:items-center md:justify-between"
            >
              <div className="flex flex-wrap items-center gap-2">
                <ShieldCheck className="h-3.5 w-3.5 text-[#38B88A]" />
                <span>Enterprise Secure</span>
                <span>•</span>
                <span>SOC 2 Type II</span>
                <span>•</span>
                <span>GDPR Compliant</span>
                <span>•</span>
                <span>ISO 27001</span>
              </div>
              <p>© 2025 CortexPrime. All rights reserved.</p>
            </motion.footer>
          </motion.div>
        </main>
      </div>
    </div>
  );
}
