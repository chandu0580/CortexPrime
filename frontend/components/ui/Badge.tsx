import { cn } from "@/utils/cn";
import type { ReactNode } from "react";

type BadgeProps = {
  children: ReactNode;
  className?: string;
};

export default function Badge({ children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border border-[#D6F0E5] bg-white/90 px-4 py-2 text-[0.9rem] font-medium tracking-[-0.02em] text-[#2F9F77] shadow-[0_8px_24px_rgba(148,163,184,0.08)] backdrop-blur",
        className,
      )}
    >
      <span className="h-2 w-2 rounded-full bg-[#38B88A]" aria-hidden="true" />
      {children}
    </span>
  );
}
