import { cn } from "@/utils/cn";

type LandingLogoProps = {
  compact?: boolean;
  className?: string;
  textClassName?: string;
};

export default function LandingLogo({
  compact = false,
  className,
  textClassName,
}: LandingLogoProps) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div
        className={cn(
          "grid place-items-center rounded-2xl border border-[#BEE8D8] bg-[#EEFBF5] text-[#38B88A] shadow-[0_10px_20px_rgba(56,184,138,0.12)]",
          compact ? "h-9 w-9" : "h-11 w-11",
        )}
      >
        <svg
          viewBox="0 0 48 48"
          aria-hidden="true"
          className={compact ? "h-5 w-5" : "h-6 w-6"}
          fill="none"
        >
          <path
            d="M24 4.5 39 13v22L24 43.5 9 35V13L24 4.5Z"
            stroke="currentColor"
            strokeWidth="3.2"
            strokeLinejoin="round"
          />
          <path
            d="M24 13 31 17v14l-7 4-7-4V17l7-4Z"
            fill="currentColor"
            fillOpacity=".18"
            stroke="currentColor"
            strokeWidth="2.6"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      <span
        className={cn(
          "text-[1.05rem] font-semibold tracking-[-0.04em] text-[#111827]",
          compact && "text-[0.95rem]",
          textClassName,
        )}
      >
        CortexPrime
      </span>
    </div>
  );
}
