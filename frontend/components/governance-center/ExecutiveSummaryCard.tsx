"use client";

import { motion } from "framer-motion";
import { govSummary } from "./mockData";
import { variants } from "@/lib/motion-tokens";
import { ShieldCheck, TrendingUp, Award, Activity, Heart } from "lucide-react";

export default function ExecutiveSummaryCard() {
  const stats = [
    {
      label: "Compliance Score",
      value: govSummary.complianceScore,
      change: "+0.3% MoM",
      icon: ShieldCheck,
      color: "text-[#38B88A]",
      bg: "bg-[#E8F5EE]",
    },
    {
      label: "Policy Coverage",
      value: govSummary.policyCoverage,
      change: "Fully mapped",
      icon: Activity,
      color: "text-blue-600",
      bg: "bg-blue-50",
    },
    {
      label: "Risk Reduction",
      value: govSummary.riskReduction,
      change: "-12% YoY",
      icon: TrendingUp,
      color: "text-[#A16207]",
      bg: "bg-amber-50",
    },
    {
      label: "Enterprise Trust Score",
      value: govSummary.trustScore,
      change: "Optimal health",
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
        <span>Enterprise AI Governance Summary</span>
      </div>

      <p className="mt-4 text-base font-semibold leading-relaxed text-[#111827]">
        CortexPrime evaluated <span className="font-extrabold text-[#38B88A]">48,216 AI actions</span> this month with a <span className="font-extrabold text-[#2F9F77]">99.7% compliance score</span>. No critical governance violations were detected. Human approval was required for <span className="font-bold text-[#111827]">2.1%</span> of high-risk operations, while policy enforcement successfully prevented <span className="font-bold text-[#B91C1C]">143 unsafe actions</span>.
      </p>

      {/* Grid of governance specific metrics */}
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
    </motion.div>
  );
}
