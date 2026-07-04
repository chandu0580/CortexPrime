import { cn } from "@/utils/cn";

type DividerProps = {
  label?: string;
  className?: string;
};

export default function Divider({ label = "OR", className }: DividerProps) {
  return (
    <div className={cn("flex items-center gap-4", className)} aria-hidden="true">
      <div className="h-px flex-1 bg-[#E5E7EB]" />
      <span className="text-[0.82rem] font-medium uppercase tracking-[0.18em] text-[#9CA3AF]">
        {label}
      </span>
      <div className="h-px flex-1 bg-[#E5E7EB]" />
    </div>
  );
}
