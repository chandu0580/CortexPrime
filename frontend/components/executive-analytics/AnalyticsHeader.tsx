"use client";

import { motion } from "framer-motion";
import { Download, FileText, Calendar, Filter, RefreshCw, ChevronDown } from "lucide-react";
import { useState } from "react";
import { dur, ease } from "@/lib/motion-tokens";

interface AnalyticsHeaderProps {
  onRefresh?: () => void;
  onGenerateSummary?: () => void;
  onExport?: () => void;
}

export default function AnalyticsHeader({
  onRefresh,
  onGenerateSummary,
  onExport,
}: AnalyticsHeaderProps) {
  const [timeRange, setTimeRange] = useState("Last 7 Days");
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
          Executive Analytics
        </h1>
        <p className="mt-1.5 text-sm font-medium text-[#6B7280]">
          Measure AI performance, operational efficiency, business impact, and enterprise adoption.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {/* Time Range Selector */}
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
          aria-label="Refresh data"
        >
          <RefreshCw className={`h-3.5 w-3.5 text-[#6B7280] ${isRefreshing ? "animate-spin text-[#38B88A]" : ""}`} />
        </button>

        {/* Generate Summary */}
        <button
          onClick={onGenerateSummary}
          className="inline-flex items-center rounded-xl border border-[#E5E7EB] bg-white px-3.5 py-2 text-xs font-semibold text-[#111827] shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-colors hover:bg-[#F9FAFB]"
        >
          <FileText className="mr-2 h-3.5 w-3.5 text-[#38B88A]" />
          Generate Executive Summary
        </button>

        {/* Export Report */}
        <button
          onClick={onExport}
          className="inline-flex items-center rounded-xl bg-[#38B88A] px-4 py-2 text-xs font-bold text-white shadow-[0_4px_14px_rgba(56,184,138,0.25)] transition-all hover:bg-[#2F9F77] hover:shadow-[0_6px_16px_rgba(56,184,138,0.3)] active:scale-[0.98]"
        >
          <Download className="mr-2 h-3.5 w-3.5" />
          Export Report
        </button>
      </div>
    </motion.div>
  );
}
