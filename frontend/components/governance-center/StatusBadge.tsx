import { cn } from "@/utils/cn";

export type GovStatusType =
  | "active"
  | "warning"
  | "draft"
  | "disabled"
  | "passed"
  | "blocked"
  | "approved"
  | "rejected"
  | "reviewed"
  | "updated"
  | "low"
  | "medium"
  | "high"
  | "critical"
  | "success"
  | "info"
  | "danger"
  | "neutral";

interface StatusBadgeProps {
  status: GovStatusType;
  children: React.ReactNode;
  className?: string;
}

export default function StatusBadge({ status, children, className }: StatusBadgeProps) {
  const styles = {
    active: "border-[#D6F0E5] bg-[#E8F5EE]/50 text-[#2F9F77]",
    passed: "border-[#D6F0E5] bg-[#E8F5EE]/50 text-[#2F9F77]",
    approved: "border-[#D6F0E5] bg-[#E8F5EE]/50 text-[#2F9F77]",
    success: "border-[#D6F0E5] bg-[#E8F5EE]/50 text-[#2F9F77]",
    
    warning: "border-[#FEF08A] bg-[#FEF9C3]/50 text-[#A16207]",
    medium: "border-[#FEF08A] bg-[#FEF9C3]/50 text-[#A16207]",
    
    draft: "border-[#E5E7EB] bg-[#F9FAFB]/50 text-[#4B5563]",
    reviewed: "border-[#E5E7EB] bg-[#F9FAFB]/50 text-[#4B5563]",
    updated: "border-[#E5E7EB] bg-[#F9FAFB]/50 text-[#4B5563]",
    low: "border-[#E5E7EB] bg-[#F9FAFB]/50 text-[#4B5563]",
    neutral: "border-[#E5E7EB] bg-[#F9FAFB]/50 text-[#4B5563]",

    disabled: "border-[#F3F4F6] bg-[#F3F4F6]/50 text-[#9CA3AF]",
    info: "border-[#BFDBFE] bg-[#EFF6FF]/50 text-[#1D4ED8]",
    
    blocked: "border-[#FCA5A5] bg-[#FEE2E2]/50 text-[#B91C1C]",
    rejected: "border-[#FCA5A5] bg-[#FEE2E2]/50 text-[#B91C1C]",
    danger: "border-[#FCA5A5] bg-[#FEE2E2]/50 text-[#B91C1C]",
    critical: "border-[#FCA5A5] bg-[#FEE2E2]/50 text-[#B91C1C]",
    high: "border-[#FCD34D] bg-[#FEF3C7]/50 text-[#B45309]",
  };

  const dotStyles = {
    active: "bg-[#38B88A]",
    passed: "bg-[#38B88A]",
    approved: "bg-[#38B88A]",
    success: "bg-[#38B88A]",
    
    warning: "bg-[#EAB308]",
    medium: "bg-[#EAB308]",
    
    draft: "bg-[#6B7280]",
    reviewed: "bg-[#6B7280]",
    updated: "bg-[#6B7280]",
    low: "bg-[#6B7280]",
    neutral: "bg-[#6B7280]",

    disabled: "bg-[#9CA3AF]",
    info: "bg-[#3B82F6]",
    
    blocked: "bg-[#EF4444]",
    rejected: "bg-[#EF4444]",
    danger: "bg-[#EF4444]",
    critical: "bg-[#EF4444]",
    high: "bg-[#F59E0B]",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold tracking-[-0.01em] backdrop-blur whitespace-nowrap",
        styles[status] || styles.draft,
        className
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full animate-blink", dotStyles[status] || dotStyles.draft)} aria-hidden="true" />
      {children}
    </span>
  );
}
