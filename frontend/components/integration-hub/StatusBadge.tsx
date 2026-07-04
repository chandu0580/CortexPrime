"use client";

import { cn } from "@/utils/cn";

export type IntegrationStatusType =
  | "Running"
  | "Completed"
  | "Queued"
  | "Failed"
  | "Retrying"
  | "Connected"
  | "Warning"
  | "Error"
  | "Disconnected"
  | "active"
  | "expired"
  | "rotating"
  | "critical"
  | "verified"
  | "healthy"
  | "success"
  | "danger"
  | "info"
  | "neutral";

interface StatusBadgeProps {
  status: IntegrationStatusType;
  children: React.ReactNode;
  className?: string;
}

export default function StatusBadge({ status, children, className }: StatusBadgeProps) {
  const normStatus = status.toLowerCase() as string;

  // Visual style definitions matching status category
  const styles: Record<string, string> = {
    // Healthy / Active / Success states
    completed: "border-[#D6F0E5] bg-[#E8F5EE]/50 text-[#2F9F77]",
    connected: "border-[#D6F0E5] bg-[#E8F5EE]/50 text-[#2F9F77]",
    active: "border-[#D6F0E5] bg-[#E8F5EE]/50 text-[#2F9F77]",
    verified: "border-[#D6F0E5] bg-[#E8F5EE]/50 text-[#2F9F77]",
    healthy: "border-[#D6F0E5] bg-[#E8F5EE]/50 text-[#2F9F77]",
    success: "border-[#D6F0E5] bg-[#E8F5EE]/50 text-[#2F9F77]",

    // Warn / In Progress states
    running: "border-[#BFDBFE] bg-[#EFF6FF]/50 text-[#1D4ED8]",
    queued: "border-[#E5E7EB] bg-[#F9FAFB]/50 text-[#4B5563]",
    retrying: "border-[#FEF08A] bg-[#FEF9C3]/50 text-[#A16207]",
    warning: "border-[#FEF08A] bg-[#FEF9C3]/50 text-[#A16207]",
    rotating: "border-[#FEF08A] bg-[#FEF9C3]/50 text-[#A16207]",
    info: "border-[#BFDBFE] bg-[#EFF6FF]/50 text-[#1D4ED8]",

    // Failure / Critical states
    failed: "border-[#FCA5A5] bg-[#FEE2E2]/50 text-[#B91C1C]",
    error: "border-[#FCA5A5] bg-[#FEE2E2]/50 text-[#B91C1C]",
    disconnected: "border-[#FCA5A5] bg-[#FEE2E2]/50 text-[#B91C1C]",
    expired: "border-[#FCA5A5] bg-[#FEE2E2]/50 text-[#B91C1C]",
    critical: "border-[#FCA5A5] bg-[#FEE2E2]/50 text-[#B91C1C]",
    danger: "border-[#FCA5A5] bg-[#FEE2E2]/50 text-[#B91C1C]",

    // Defaults
    neutral: "border-[#E5E7EB] bg-[#F9FAFB]/50 text-[#4B5563]",
  };

  const dotStyles: Record<string, string> = {
    completed: "bg-[#38B88A]",
    connected: "bg-[#38B88A]",
    active: "bg-[#38B88A]",
    verified: "bg-[#38B88A]",
    healthy: "bg-[#38B88A]",
    success: "bg-[#38B88A]",

    running: "bg-[#3B82F6] animate-pulse",
    queued: "bg-[#6B7280]",
    retrying: "bg-[#EAB308]",
    warning: "bg-[#EAB308]",
    rotating: "bg-[#EAB308]",
    info: "bg-[#3B82F6]",

    failed: "bg-[#EF4444]",
    error: "bg-[#EF4444]",
    disconnected: "bg-[#EF4444]",
    expired: "bg-[#EF4444]",
    critical: "bg-[#EF4444]",
    danger: "bg-[#EF4444]",

    neutral: "bg-[#6B7280]",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold tracking-[-0.01em] backdrop-blur whitespace-nowrap",
        styles[normStatus] || styles.neutral,
        className
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", dotStyles[normStatus] || dotStyles.neutral)} aria-hidden="true" />
      {children}
    </span>
  );
}
