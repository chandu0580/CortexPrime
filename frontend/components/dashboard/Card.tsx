import { cn } from "@/utils/cn"

export function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("rounded-[20px] border border-[#EAEFF5] bg-white shadow-[0_2px_16px_rgba(148,163,184,0.08)]", className)}>
      {children}
    </div>
  )
}
