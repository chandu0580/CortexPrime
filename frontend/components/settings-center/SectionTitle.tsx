import { cn } from "@/utils/cn";

interface SectionTitleProps {
  title: string;
  subtitle?: string;
  className?: string;
}

export default function SectionTitle({ title, subtitle, className }: SectionTitleProps) {
  return (
    <div className={cn("mb-6", className)}>
      <h2 className="text-[1.125rem] font-bold tracking-tight text-[#111827]">
        {title}
      </h2>
      {subtitle && (
        <p className="mt-1 text-xs text-[#6B7280] font-medium">
          {subtitle}
        </p>
      )}
    </div>
  );
}
