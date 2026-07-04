"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Download, Filter, RefreshCw, Calendar, ChevronDown, CheckCircle2 } from "lucide-react";
import { dur, ease } from "@/lib/motion-tokens";

interface MonitoringHeaderProps {
  onExportMetrics?: () => void;
  onRefresh?: () => void;
}

export default function MonitoringHeader({
  onExportMetrics,
  onRefresh,
}: MonitoringHeaderProps) {
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefreshClick = () => {
    setIsRefreshing(true);
    if (onRefresh) onRefresh();
    setTimeout(() => setIsRefreshing(false), 800);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: dur.base, ease: ease.out }}
      className="flex flex-col gap-4 border-b border-[#E5E7EB] pb-5 md:flex-row md:items-center md:justify-between"
    >
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-[#111827]">
          Operations Monitoring
        </h1>
        <p className="mt-1.5 text-sm font-medium text-[#6B7280]">
          Monitor the health, performance, and availability of the CortexPrime AI Operating System in real time.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {/* System Health State indicator */}
        <div className="inline-flex items-center gap-1.5 rounded-xl border border-[#D6F0E5] bg-[#E8F5EE] px-3.5 py-2 text-xs font-bold text-[#2F9F77] shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
          <CheckCircle2 className="h-3.5 w-3.5 text-[#38B88A]" />
          <span>System Healthy</span>
        </div>

        {/* Date Selector */}
        <div className="relative inline-flex items-center rounded-xl border border-[#E5E7EB] bg-white px-3.5 py-2 text-xs font-semibold text-[#111827] shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-colors hover:bg-[#F9FAFB]">
          <Calendar className="mr-2 h-3.5 w-3.5 text-[#6B7280]" />
          <span>May 6 – May 12, 2024</span>
          <ChevronDown className="ml-1.5 h-3 w-3 text-[#6B7280]" />
        </div>

        {/* Filters */}
        <button className="inline-flex items-center rounded-xl border border-[#E5E7EB] bg-white px-3.5 py-2 text-xs font-semibold text-[#111827] shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-colors hover:bg-[#F9FAFB]">
          <Filter className="mr-2 h-3.5 w-3.5 text-[#6B7280]" />
          Filters
        </button>

        {/* Refresh */}
        <button
          onClick={handleRefreshClick}
          className="inline-flex items-center justify-center rounded-xl border border-[#E5E7EB] bg-white p-2.5 text-[#111827] shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-colors hover:bg-[#F9FAFB] focus:outline-none"
          aria-label="Refresh operational metrics"
        >
          <RefreshCw className={`h-3.5 w-3.5 text-[#6B7280] ${isRefreshing ? "animate-spin text-[#38B88A]" : ""}`} />
        </button>

        {/* Export Metrics */}
        <button
          onClick={onExportMetrics}
          className="inline-flex items-center rounded-xl bg-[#38B88A] px-4 py-2 text-xs font-bold text-white shadow-[0_4px_14px_rgba(56,184,138,0.25)] transition-all hover:bg-[#2F9F77] hover:shadow-[0_6px_16px_rgba(56,184,138,0.3)] active:scale-[0.98]"
        >
          <Download className="mr-1.5 h-4 w-4" />
          Export Metrics
        </button>
      </div>
    </motion.div>
  );
}
