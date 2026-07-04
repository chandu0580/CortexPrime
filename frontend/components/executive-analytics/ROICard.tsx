"use client";

import { motion } from "framer-motion";
import { variants } from "@/lib/motion-tokens";
import { Clock, TrendingUp, DollarSign, Award, CheckCircle2 } from "lucide-react";

export default function ROICard() {
  const stats = [
    {
      label: "Estimated Time Saved",
      value: "1,822 hours",
      change: "+24% MoM",
      icon: Clock,
      color: "text-[#38B88A]",
      bg: "bg-[#E8F5EE]",
    },
    {
      label: "Operational Efficiency",
      value: "94.2/100",
      change: "+4.7% MoM",
      icon: TrendingUp,
      color: "text-[#2F9F77]",
      bg: "bg-[#E8F5EE]/80",
    },
    {
      label: "Avg Execution Cost",
      value: "$0.12 / mission",
      change: "-11% YoY",
      icon: DollarSign,
      color: "text-[#A16207]",
      bg: "bg-amber-50",
    },
    {
      label: "Business Value Generated",
      value: "$178,500",
      change: "+15.6% MTD",
      icon: Award,
      color: "text-blue-600",
      bg: "bg-blue-50",
    },
  ];

  return (
    <motion.div
      whileHover={variants.cardHover}
      className="rounded-[24px] border border-[#D6F0E5] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)] transition-shadow duration-200 hover:shadow-[0_12px_36px_rgba(56,184,138,0.08)]"
    >
      <div className="flex items-center gap-2 text-sm font-bold text-[#2F9F77]">
        <CheckCircle2 className="h-5 w-5 text-[#38B88A]" />
        <span>Enterprise AI ROI Executive Summary</span>
      </div>

      <p className="mt-4 text-base font-semibold leading-relaxed text-[#111827]">
        CortexPrime executed <span className="font-extrabold text-[#38B88A]">14,862 autonomous missions</span> this month with a <span className="font-extrabold text-[#2F9F77]">98.9% success rate</span>. Engineering achieved the highest adoption, reducing operational effort by an estimated <span className="font-extrabold text-[#111827]">640 hours</span>. Overall AI ROI increased by <span className="font-extrabold text-[#2F9F77]">24%</span> while average execution cost decreased by <span className="font-extrabold text-[#A16207]">11%</span>.
      </p>

      {/* Grid of ROI specific metrics */}
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
              <span className={`mt-0.5 inline-block text-[10px] font-bold ${
                stat.change.includes("-") ? "text-[#38B88A]" : "text-[#2F9F77]"
              }`}>
                {stat.change}
              </span>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}
