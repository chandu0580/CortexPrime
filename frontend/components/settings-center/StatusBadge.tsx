"use client";

import { cn } from "@/utils/cn";

export type SettingsStatusType =
  | "Active"
  | "Deactivated"
  | "Expired"
  | "Revoked"
  | "Connected"
  | "Disconnected"
  | "Enabled"
  | "Disabled"
  | "healthy"
  | "degraded"
  | "offline";

interface StatusBadgeProps {
  status: SettingsStatusType;
  children: React.ReactNode;
  className?: string;
}

export default function StatusBadge({ status, children, className }: StatusBadgeProps) {
  const normStatus = status.toLowerCase();

  const styles: Record<string, string> = {
    // Green (Success / Active)
    active: "border-[#D6F0E5] bg-[#E8F5EE]/50 text-[#2F9F77]",
    connected: "border-[#D6F0E5] bg-[#E8F5EE]/50 text-[#2F9F77]",
    enabled: "border-[#D6F0E5] bg-[#E8F5EE]/50 text-[#2F9F77]",
    healthy: "border-[#D6F0E5] bg-[#E8F5EE]/50 text-[#2F9F77]",

    // Orange/Yellow (Warnings / Inactive)
    deactivated: "border-[#FEF08A] bg-[#FEF9C3]/50 text-[#A16207]",
    disabled: "border-[#E5E7EB] bg-[#F9FAFB]/50 text-[#6B7280]",
    degraded: "border-[#FEF08A] bg-[#FEF9C3]/50 text-[#A16207]",

    // Red (Critical / Errors)
    expired: "border-[#FCA5A5] bg-[#FEE2E2]/50 text-[#B91C1C]",
    revoked: "border-[#FCA5A5] bg-[#FEE2E2]/50 text-[#B91C1C]",
    disconnected: "border-[#FCA5A5] bg-[#FEE2E2]/50 text-[#B91C1C]",
    offline: "border-[#FCA5A5] bg-[#FEE2E2]/50 text-[#B91C1C]",

    // Default
    neutral: "border-[#E5E7EB] bg-[#F9FAFB]/50 text-[#4B5563]",
  };

  const dotStyles: Record<string, string> = {
    active: "bg-[#38B88A]",
    connected: "bg-[#38B88A]",
    enabled: "bg-[#38B88A]",
    healthy: "bg-[#38B88A]",

    deactivated: "bg-[#EAB308]",
    disabled: "bg-[#9CA3AF]",
    degraded: "bg-[#EAB308]",

    expired: "bg-[#EF4444]",
    revoked: "bg-[#EF4444]",
    disconnected: "bg-[#EF4444]",
    offline: "bg-[#EF4444]",

    neutral: "bg-[#6B7280]",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.25 rounded-full border px-2 py-0.5 text-[10px] font-bold tracking-tight whitespace-nowrap",
        styles[normStatus] || styles.neutral,
        className
      )}
    >
      <span className={cn("h-1 w-1 rounded-full", dotStyles[normStatus] || dotStyles.neutral)} aria-hidden="true" />
      {children}
    </span>
  );
}
