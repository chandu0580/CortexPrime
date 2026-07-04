"use client";

import { motion } from "framer-motion";
import { integrationInsights } from "./mockData";
import { variants } from "@/lib/motion-tokens";
import { ShieldCheck, Activity, Brain, Clock, ShieldAlert, Zap } from "lucide-react";
import { cn } from "@/utils/cn";

export default function InsightCard() {
  const getIcon = (type: string) => {
    switch (type) {
      case "Most Active":
        return Activity;
      case "Highest API Usage":
        return Brain;
      case "Slowest Integration":
        return Clock;
      case "Sync Recommendation":
        return Zap;
      case "Security Alert":
        return ShieldAlert;
      default:
        return ShieldCheck;
    }
  };

  const getColorStyles = (type: string) => {
    switch (type) {
      case "Security Alert":
        return {
          iconColor: "text-red-600",
          iconBg: "bg-red-50",
          border: "border-red-100 hover:border-red-300/40",
          recommendationBg: "bg-red-50/50 text-red-800 border-red-100",
        };
      case "Sync Recommendation":
        return {
          iconColor: "text-amber-600",
          iconBg: "bg-amber-50",
          border: "border-amber-100 hover:border-amber-300/40",
          recommendationBg: "bg-amber-50/50 text-amber-800 border-amber-100",
        };
      default:
        return {
          iconColor: "text-[#38B88A]",
          iconBg: "bg-[#E8F5EE]",
          border: "border-[#E5E7EB] hover:border-[#38B88A]/40",
          recommendationBg: "bg-[#E8F5EE]/50 text-[#2F9F77] border-[#D6F0E5]",
        };
    }
  };

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
      {integrationInsights.map((insight, index) => {
        const Icon = getIcon(insight.type);
        const styles = getColorStyles(insight.type);

        return (
          <motion.div
            key={insight.title}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: index * 0.05 }}
            whileHover={variants.cardHover}
            className={cn(
              "flex flex-col justify-between rounded-[24px] border bg-white p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] transition-all duration-200",
              styles.border
            )}
          >
            {/* Header row */}
            <div>
              <div className="flex items-center gap-2.5 text-xs font-bold text-[#6B7280]">
                <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg", styles.iconBg, styles.iconColor)}>
                  <Icon className="h-4 w-4" />
                </div>
                <span>{insight.title}</span>
              </div>

              {/* Large Metric Value */}
              <h4 className="mt-4 text-xl font-extrabold text-[#111827]">
                {insight.value}
              </h4>
              <p className="mt-1.5 text-xs font-semibold leading-relaxed text-[#6B7280]">
                {insight.description}
              </p>
            </div>

            {/* Actionable recommendation box */}
            <div className={cn("mt-4 rounded-xl border p-3 text-xs font-semibold leading-relaxed", styles.recommendationBg)}>
              <span className="block text-[9px] font-extrabold uppercase tracking-wider mb-0.5 opacity-80">Recommendation</span>
              {insight.recommendation}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
