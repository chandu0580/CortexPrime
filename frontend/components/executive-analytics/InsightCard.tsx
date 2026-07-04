"use client";

import { motion } from "framer-motion";
import { businessInsights } from "./mockData";
import { variants } from "@/lib/motion-tokens";
import { Award, Compass, Clock, AlertTriangle, Cpu, TrendingUp } from "lucide-react";

export default function InsightCard() {
  const getIcon = (type: string) => {
    switch (type) {
      case "department":
        return Award;
      case "capability":
        return Compass;
      case "productivity":
        return Clock;
      case "cost":
        return AlertTriangle;
      case "optimization":
        return Cpu;
      case "savings":
        return TrendingUp;
      default:
        return Compass;
    }
  };

  const getStyles = (type: string) => {
    switch (type) {
      case "cost":
        return {
          bg: "bg-white border-[#EF4444]/20",
          iconBg: "bg-[#FEF2F2]",
          iconColor: "text-[#EF4444]",
          badge: "bg-[#FEF2F2] border-[#FCA5A5] text-[#B91C1C]",
        };
      case "productivity":
      case "savings":
      case "department":
        return {
          bg: "bg-white border-[#38B88A]/20",
          iconBg: "bg-[#E8F5EE]",
          iconColor: "text-[#38B88A]",
          badge: "bg-[#E8F5EE] border-[#D6F0E5] text-[#2F9F77]",
        };
      default:
        return {
          bg: "bg-white border-[#E5E7EB]",
          iconBg: "bg-[#F3F4F6]",
          iconColor: "text-[#6B7280]",
          badge: "bg-[#F3F4F6] border-[#E5E7EB] text-[#4B5563]",
        };
    }
  };

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {businessInsights.map((insight, index) => {
        const Icon = getIcon(insight.type);
        const style = getStyles(insight.type);

        return (
          <motion.div
            key={insight.id}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: index * 0.05 }}
            whileHover={variants.cardHover}
            className={`flex flex-col justify-between rounded-[24px] border p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] transition-shadow duration-200 hover:shadow-[0_12px_36px_rgba(56,184,138,0.06)] ${style.bg}`}
          >
            <div>
              {/* Header */}
              <div className="flex items-center justify-between border-b border-[#F3F4F6] pb-3">
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#6B7280]">
                  {insight.title}
                </span>
                <span className={`rounded-full border px-2 py-0.5 text-[9px] font-extrabold tracking-[-0.01em] ${style.badge}`}>
                  {insight.badgeText}
                </span>
              </div>

              {/* Metric & Info */}
              <div className="mt-4 flex items-start gap-3">
                <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${style.iconBg} ${style.iconColor}`}>
                  <Icon className="h-5 w-5" />
                </div>
                <div>
                  <h4 className="text-lg font-extrabold text-[#111827]">
                    {insight.metric}
                  </h4>
                  <p className="mt-1 text-xs font-semibold text-[#6B7280] leading-relaxed">
                    {insight.subtext}
                  </p>
                </div>
              </div>
            </div>

            {/* Recommendation Actionable Footer */}
            <div className="mt-5 rounded-xl bg-[#F8FAFC] border border-[#E5E7EB] p-3 text-[11px] font-semibold text-[#111827]">
              <span className="block text-[9px] font-bold uppercase tracking-wider text-[#6B7280] mb-0.5">Recommendation</span>
              {insight.recommendation}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
