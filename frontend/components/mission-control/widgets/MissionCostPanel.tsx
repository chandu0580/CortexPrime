"use client"

import { useQuery } from "@tanstack/react-query"
import { api } from "@/services/api"
import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { InfoCard } from "@/components/mission-control/shared/InfoCard"

export function MissionCostPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ["mission-cost", "summary"],
    queryFn: () => api.get<Record<string, unknown>>("/api/costs/summary"),
    refetchInterval: 60_000,
  })

  const today = (data?.today ?? data?.total_today ?? 0) as number
  const month = (data?.month ?? data?.total_month ?? 0) as number
  const topMission = data?.top_mission as string | undefined
  const providerCosts = data?.provider_costs as Record<string, number> | undefined

  return (
    <section>
      <SectionHeader title="Mission Cost" suffix={<span className="text-[0.7rem] text-[#B0B7C3]">Cost Engine</span>} />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <InfoCard label="Today">
          {isLoading ? (
            <div className="h-6 w-16 rounded bg-[#F0F4F8]" />
          ) : (
            <p className="text-[1.1rem] font-bold text-[#111827]">
              {today != null ? `$${Number(today).toFixed(2)}` : "N/A"}
            </p>
          )}
        </InfoCard>
        <InfoCard label="This Month">
          {isLoading ? (
            <div className="h-6 w-16 rounded bg-[#F0F4F8]" />
          ) : (
            <p className="text-[1.1rem] font-bold text-[#111827]">
              {month != null ? `$${Number(month).toFixed(2)}` : "N/A"}
            </p>
          )}
        </InfoCard>
        <InfoCard label="Top Mission">
          {isLoading ? (
            <div className="h-6 w-24 rounded bg-[#F0F4F8]" />
          ) : (
            <div>
              <p className="text-[0.78rem] font-medium text-[#111827] truncate">
                {topMission ?? "N/A"}
              </p>
              {providerCosts && (
                <div className="mt-2 space-y-1">
                  {Object.entries(providerCosts).slice(0, 3).map(([provider, cost]) => (
                    <div key={provider} className="flex items-center justify-between text-[0.65rem]">
                      <span className="text-[#9CA3AF]">{provider}</span>
                      <span className="font-medium text-[#111827]">${Number(cost).toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </InfoCard>
      </div>
    </section>
  )
}
