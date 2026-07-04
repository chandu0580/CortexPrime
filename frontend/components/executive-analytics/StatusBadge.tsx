import { cn } from "@/utils/cn";

export type StatusType = "success" | "warning" | "danger" | "info" | "neutral";

interface StatusBadgeProps {
  status: StatusType;
  children: React.ReactNode;
  className?: string;
}

export default function StatusBadge({ status, children, className }: StatusBadgeProps) {
  const styles = {
    success: "border-[#D6F0E5] bg-[#E8F5EE]/50 text-[#2F9F77]",
    warning: "border-[#FEF08A] bg-[#FEF9C3]/50 text-[#A16207]",
    danger: "border-[#FCA5A5] bg-[#FEE2E2]/50 text-[#B91C1C]",
    info: "border-[#BFDBFE] bg-[#EFF6FF]/50 text-[#1D4ED8]",
    neutral: "border-[#E5E7EB] bg-[#F9FAFB]/50 text-[#4B5563]",
  };

  const dotStyles = {
    success: "bg-[#38B88A]",
    warning: "bg-[#EAB308]",
    danger: "bg-[#EF4444]",
    info: "bg-[#3B82F6]",
    neutral: "bg-[#6B7280]",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold tracking-[-0.01em] backdrop-blur",
        styles[status],
        className
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full animate-blink", dotStyles[status])} aria-hidden="true" />
      {children}
    </span>
  );
}
