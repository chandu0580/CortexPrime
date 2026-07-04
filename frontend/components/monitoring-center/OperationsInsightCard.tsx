"use client";

import { motion } from "framer-motion";
import { opsSummary } from "./mockData";
import { variants } from "@/lib/motion-tokens";
import { ShieldCheck, TrendingUp, DollarSign, Activity, AlertCircle, Heart } from "lucide-react";

export default function OperationsInsightCard() {
  const stats = [
    {
      label: "Platform Availability",
      value: opsSummary.availability,
      change: "Target: 99.99%",
      icon: ShieldCheck,
      color: "text-[#38B88A]",
      bg: "bg-[#E8F5EE]",
    },
    {
      label: "Active Incidents",
      value: opsSummary.incidentCount,
      change: "0 critical cases",
      icon: AlertCircle,
      color: "text-blue-600",
      bg: "bg-blue-50",
    },
    {
      label: "Avg Recovery Time",
      value: opsSummary.avgRecoveryTime,
      change: "98% auto-healed",
      icon: TrendingUp,
      color: "text-[#A16207]",
      bg: "bg-amber-50",
    },
    {
      label: "Overall Health Score",
      value: opsSummary.healthScore,
      change: "Optimal status",
      icon: Heart,
      color: "text-[#2F9F77]",
      bg: "bg-[#E8F5EE]/80",
    },
  ];

  return (
    <motion.div
      whileHover={variants.cardHover}
      className="rounded-[24px] border border-[#D6F0E5] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)] transition-shadow duration-200 hover:shadow-[0_12px_36px_rgba(56,184,138,0.08)]"
    >
      <div className="flex items-center gap-2 text-sm font-bold text-[#2F9F77]">
        <ShieldCheck className="h-5 w-5 text-[#38B88A]" />
        <span>Enterprise operations SRE Insights</span>
      </div>

      <p className="mt-4 text-base font-semibold leading-relaxed text-[#111827]">
        All CortexPrime services are operating normally with <span className="font-extrabold text-[#38B88A]">99.98% availability</span>. Average API latency is <span className="font-extrabold text-[#2F9F77]">82 ms</span>, infrastructure utilization remains within expected thresholds, and no critical incidents are currently active. Voice Runtime recovered automatically after a transient reconnect event with no customer impact.
      </p>

      {/* Grid of operational specific metrics */}
      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.label}
              className="rounded-2xl border border-[#E5E7EB] bg-[#F8FAFC] p-4 transition-all duration-200 hover:bg-white hover:shadow-[0_4px_12px_rgba(0,0,0,0.03)]"
            >
              <div className="flex items-center gap-2">
                <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${stat.bg} ${stat.color}`}>
                  <Icon className="h-4 w-4" />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#6B7280]">
                  {stat.label}
                </span>
              </div>
              <p className="mt-2.5 text-lg font-extrabold text-[#111827]">
                {stat.value}
              </p>
              <span className="mt-0.5 inline-block text-[10px] font-semibold text-[#6B7280]">
                {stat.change}
              </span>
            </div>
          );
        })}
      </div>

      {/* SRE Actionable recommendation */}
      <div className="mt-5 rounded-xl bg-[#FFFBEB] border border-[#FEF08A] p-4 text-xs font-semibold text-[#B45309]">
        <span className="block text-[10px] font-bold uppercase tracking-wider text-[#A16207] mb-1">Operational SRE Recommendation</span>
        {opsSummary.recommendation}
      </div>
    </motion.div>
  );
}
