"use client";

import { motion } from "framer-motion";
import { opsExecutiveSummary } from "./mockData";
import { variants } from "@/lib/motion-tokens";
import { ShieldCheck, Network, Award, Zap, Activity } from "lucide-react";

export default function ExecutiveSummaryCard() {
  const metrics = [
    {
      label: "Connectivity Score",
      value: opsExecutiveSummary.connectivityScore,
      change: "Target: >99.0%",
      icon: Award,
      color: "text-[#38B88A]",
      bg: "bg-[#E8F5EE]",
    },
    {
      label: "API Success Rate",
      value: opsExecutiveSummary.apiSuccessRate,
      change: "Over 2.3M requests",
      icon: Activity,
      color: "text-blue-600",
      bg: "bg-blue-50",
    },
    {
      label: "Connected Platforms",
      value: `${opsExecutiveSummary.connectedPlatforms} Systems`,
      change: "All environments active",
      icon: Network,
      color: "text-purple-600",
      bg: "bg-purple-50",
    },
    {
      label: "Sync Reliability",
      value: opsExecutiveSummary.syncReliability,
      change: "Target: >99.9%",
      icon: Zap,
      color: "text-amber-600",
      bg: "bg-amber-50",
    },
  ];

  return (
    <motion.div
      whileHover={variants.cardHover}
      className="rounded-[24px] border border-[#D6F0E5] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)] transition-shadow duration-200 hover:shadow-[0_12px_36px_rgba(56,184,138,0.08)] animate-fade-in"
    >
      <div className="flex items-center gap-2 text-sm font-bold text-[#2F9F77]">
        <ShieldCheck className="h-5 w-5 text-[#38B88A]" />
        <span>Enterprise Connectivity Status Summary</span>
      </div>

      <p className="mt-4 text-base font-semibold leading-relaxed text-[#111827]">
        CortexPrime is successfully connected to <span className="font-extrabold text-[#38B88A]">{opsExecutiveSummary.connectedPlatforms} enterprise systems</span> with an overall integration health score of <span className="font-extrabold text-[#2F9F77]">{opsExecutiveSummary.connectivityScore}</span>. Over <span className="font-extrabold text-[#111827]">2.3 million API requests</span> were processed this week with a <span className="font-extrabold text-[#38B88A]">{opsExecutiveSummary.apiSuccessRate} success rate</span>. All critical business environments remain synchronized and operational.
      </p>

      {/* Grid of integration-specific metrics */}
      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <div
              key={metric.label}
              className="rounded-2xl border border-[#E5E7EB] bg-[#F8FAFC] p-4 transition-all duration-200 hover:bg-white hover:shadow-[0_4px_12px_rgba(0,0,0,0.03)]"
            >
              <div className="flex items-center gap-2">
                <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${metric.bg} ${metric.color}`}>
                  <Icon className="h-4 w-4" />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#6B7280]">
                  {metric.label}
                </span>
              </div>
              <p className="mt-2.5 text-lg font-extrabold text-[#111827]">
                {metric.value}
              </p>
              <span className="mt-0.5 inline-block text-[10px] font-semibold text-[#6B7280]">
                {metric.change}
              </span>
            </div>
          );
        })}
      </div>

      {/* SRE Actionable recommendation */}
      <div className="mt-5 rounded-xl bg-[#FFFBEB] border border-[#FEF08A] p-4 text-xs font-semibold text-[#B45309]">
        <span className="block text-[10px] font-bold uppercase tracking-wider text-[#A16207] mb-1">Enterprise Connectivity Recommendation</span>
        {opsExecutiveSummary.recommendation}
      </div>
    </motion.div>
  );
}
