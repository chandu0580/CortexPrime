"use client"

import Image from "next/image";
import Link from "next/link";
import { useMemo } from "react";
import { motion } from "framer-motion";
import { Bell, ChevronDown, Mic, Search, Target } from "lucide-react";
import { cn } from "@/utils/cn";
import { Badge } from "./Badge";
import type { StatusTone } from "@/components/dashboard/data";
import type { HeaderStatus } from "@/services/dashboard/header";

export function ExecutiveHeader({ collapsed, data }: { collapsed: boolean; data?: HeaderStatus }) {
  const avatar = useMemo(() =>
    `data:image/svg+xml;utf8,${encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80"><rect width="80" height="80" rx="20" fill="#ECFBF4"/><circle cx="40" cy="30" r="14" fill="#38B88A"/><path d="M18 70c4-15 14-22 22-22s18 7 22 22" fill="#2F9F77"/></svg>`,
    )}`, []);

  const missionName = data?.currentMission ?? "No Active Mission";
  const missionTone: StatusTone = data?.missionState === "running" ? "running"
    : data?.missionState === "completed" ? "completed"
    : data?.missionState === "idle" ? "idle"
    : "idle";
  const missionLabel = data?.missionState === "running" ? "Running"
    : data?.missionState === "completed" ? "Completed"
    : data?.missionState === "idle" ? "Idle"
    : "Unknown";

  const voiceLabel = data?.voiceConnected ? "Listening..." : "Voice Offline";
  const voiceActive = data?.voiceConnected ?? false;

  const userName = data?.currentUser?.name ?? "Alex Morgan";
  const userRole = data?.currentUser?.role ?? "Enterprise Admin";
  const notifCount = data?.notificationCount ?? 0;

  return (
    <header
      className={cn(
        "sticky top-0 z-30 flex items-center gap-3 border-b border-[#EAEFF5] bg-white/96 px-5 py-3 backdrop-blur transition-all duration-300",
        collapsed ? "pl-[80px]" : "pl-[232px]",
      )}
    >
      {/* Search */}
      <label className="relative flex h-10 w-[240px] shrink-0 items-center">
        <Search className="pointer-events-none absolute left-3.5 h-4 w-4 text-[#9CA3AF]" />
        <input
          type="search"
          placeholder="Search anything..."
          className="h-full w-full rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] pl-10 pr-14 text-[0.86rem] text-[#111827] outline-none placeholder:text-[#9CA3AF] focus:border-[#B7E5D3] focus:ring-2 focus:ring-[#EAF8F1]"
        />
        <span className="absolute right-3 rounded-[7px] border border-[#E5E7EB] bg-white px-1.5 py-0.5 text-[0.66rem] font-semibold text-[#9CA3AF]">⌘K</span>
      </label>

      {/* Current Mission chip */}
      <div className="hidden items-center gap-2.5 rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] px-3 py-1.5 xl:flex">
        <div className="flex h-7 w-7 items-center justify-center rounded-[10px] bg-[#ECFBF4] text-[#38B88A]">
          <Target className="h-3.5 w-3.5" />
        </div>
        <div>
          <p className="text-[0.66rem] font-medium text-[#9CA3AF]">Current Mission</p>
          <p className="truncate max-w-[160px] text-[0.8rem] font-semibold text-[#111827]">{missionName}</p>
        </div>
        <Badge tone={missionTone}>{missionLabel}</Badge>
        <ChevronDown className="h-3.5 w-3.5 text-[#9CA3AF]" />
      </div>

      {/* Voice status chip */}
      <div className="hidden items-center gap-2.5 rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] px-3 py-1.5 lg:flex">
        <div className="flex h-7 w-7 items-center justify-center rounded-[10px] bg-[#ECFBF4] text-[#38B88A]">
          <Mic className="h-3.5 w-3.5" />
        </div>
        <div>
          <p className="text-[0.66rem] font-medium text-[#9CA3AF]">Voice Status</p>
          <p className="text-[0.8rem] font-semibold text-[#111827]">{voiceLabel}</p>
        </div>
        {voiceActive && (
          <motion.span
            animate={{ opacity: [1, 0.4, 1] }}
            transition={{ duration: 1.5, repeat: Infinity }}
            className="h-2 w-2 rounded-full bg-[#38B88A] shadow-[0_0_5px_#38B88A]"
          />
        )}
      </div>

      <div className="ml-auto flex items-center gap-2.5">
        {/* Bell */}
        <button className="relative flex h-9 w-9 items-center justify-center rounded-[12px] border border-[#EAEFF5] bg-white text-[#374151] hover:bg-[#F8FAFC]">
          <Bell className="h-4 w-4" />
          {notifCount > 0 && (
            <span className="absolute right-1.5 top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-[#EF4444] text-[0.56rem] font-bold text-white">
              {notifCount > 9 ? "9+" : notifCount}
            </span>
          )}
        </button>

        {/* Avatar */}
        <Link
          href="/settings"
          className="flex items-center gap-2.5 rounded-[14px] border border-[#EAEFF5] bg-white px-2.5 py-1.5 transition hover:bg-[#F8FAFC]"
        >
          <Image src={avatar} alt={userName} width={32} height={32} className="rounded-[10px]" />
          <div className="hidden xl:block">
            <p className="text-[0.82rem] font-semibold text-[#111827]">{userName}</p>
            <p className="text-[0.7rem] text-[#9CA3AF]">{userRole}</p>
          </div>
          <ChevronDown className="h-3.5 w-3.5 text-[#9CA3AF]" />
        </Link>
      </div>
    </header>
  );
}
