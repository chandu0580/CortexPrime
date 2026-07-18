"use client";

import { motion } from "framer-motion";
import { departmentAdoption } from "./dashboardData";
import { variants } from "@/lib/motion-tokens";
import { Users, Zap, Clock, TrendingUp } from "lucide-react";

export default function DepartmentCard() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {departmentAdoption.map((dept, index) => {
        return (
          <motion.div
            key={dept.department}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: index * 0.05 }}
            whileHover={variants.cardHover}
            className="rounded-[24px] border border-[#E5E7EB] bg-white p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] transition-shadow duration-200 hover:shadow-[0_12px_36px_rgba(56,184,138,0.06)]"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-[#F3F4F6] pb-3">
              <span className="text-sm font-extrabold text-[#111827]">
                {dept.department}
              </span>
              <div className="flex items-center gap-1 rounded-full bg-[#E8F5EE] px-2 py-0.5 text-[10px] font-bold text-[#2F9F77]">
                <TrendingUp className="h-3 w-3" />
                <span>{dept.adoptionScore}% Adoption</span>
              </div>
            </div>

            {/* Stats list */}
            <div className="mt-4 flex flex-col gap-3">
              {/* Active Users */}
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#6B7280]">
                  <Users className="h-3.5 w-3.5" />
                  Active Users
                </span>
                <span className="text-xs font-bold text-[#111827]">
                  {dept.activeUsers}
                </span>
              </div>

              {/* AI Missions */}
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#6B7280]">
                  <Zap className="h-3.5 w-3.5 text-[#38B88A]" />
                  AI Missions
                </span>
                <span className="text-xs font-bold text-[#111827]">
                  {dept.missions.toLocaleString()}
                </span>
              </div>

              {/* Time Saved */}
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#6B7280]">
                  <Clock className="h-3.5 w-3.5 text-[#A16207]" />
                  Time Saved
                </span>
                <span className="text-xs font-extrabold text-[#2F9F77]">
                  {dept.timeSaved}
                </span>
              </div>
            </div>

            {/* Adoption progress bar */}
            <div className="mt-4">
              <div className="flex items-center justify-between text-[10px] font-semibold text-[#6B7280]">
                <span>Progress Score</span>
                <span>{dept.adoptionScore}/100</span>
              </div>
              <div className="mt-1 h-1.5 w-full rounded-full bg-[#F3F4F6]">
                <div
                  className="h-full rounded-full bg-[#38B88A]"
                  style={{ width: `${dept.adoptionScore}%` }}
                />
              </div>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
