"use client"

import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from "react"
import { LiveDataService } from "./platformService"

export interface EnterpriseData {
  health: Record<string, unknown> | null
  systemHealth: Record<string, unknown> | null
  runtimeTelemetry: Record<string, unknown> | null
  runtimeInfrastructure: Record<string, unknown> | null
  executiveSnapshot: Record<string, unknown> | null
  executiveAnalytics: Record<string, unknown> | null
  memoryStatus: Record<string, unknown> | null
  graphHealth: Record<string, unknown> | null
  approvalSummary: Record<string, unknown> | null
  securityStatus: Record<string, unknown> | null
  costSummary: Record<string, unknown> | null
  governanceOverview: Record<string, unknown> | null
  isLoading: boolean
  lastRefresh: string | null
  errors: string[]
  refreshAll: () => Promise<void>
}

const EnterpriseContext = createContext<EnterpriseData>({
  health: null, systemHealth: null, runtimeTelemetry: null, runtimeInfrastructure: null,
  executiveSnapshot: null, executiveAnalytics: null, memoryStatus: null, graphHealth: null,
  approvalSummary: null, securityStatus: null, costSummary: null, governanceOverview: null,
  isLoading: true, lastRefresh: null, errors: [], refreshAll: async () => {},
})

export function useEnterpriseData() {
  return useContext(EnterpriseContext)
}

export function EnterpriseDataProvider({ children, refreshIntervalMs = 15000 }: { children: ReactNode; refreshIntervalMs?: number }) {
  const [data, setData] = useState<Omit<EnterpriseData, "isLoading" | "lastRefresh" | "errors" | "refreshAll">>({
    health: null, systemHealth: null, runtimeTelemetry: null, runtimeInfrastructure: null,
    executiveSnapshot: null, executiveAnalytics: null, memoryStatus: null, graphHealth: null,
    approvalSummary: null, securityStatus: null, costSummary: null, governanceOverview: null,
  })
  const [isLoading, setIsLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState<string | null>(null)
  const [errors, setErrors] = useState<string[]>([])

  const refreshAll = useCallback(async () => {
    setIsLoading(true)
    setErrors([])

    const results = await Promise.allSettled([
      LiveDataService.getHealth(),
      LiveDataService.getSystemHealth(),
      LiveDataService.getRuntimeTelemetry(),
      LiveDataService.getRuntimeInfrastructure(),
      LiveDataService.getExecutiveSnapshot(),
      LiveDataService.getExecutiveAnalytics(),
      LiveDataService.getMemoryStatus(),
      LiveDataService.getGraphHealth(),
      LiveDataService.getApprovalSummary(),
      LiveDataService.getSecurityStatus(),
      LiveDataService.getCostSummary(),
      LiveDataService.getGovernanceOverview(),
    ])

    const parsed = results.map((r) => r.status === "fulfilled" ? r.value.data : null)
    const errs = results
      .map((r) => r.status === "fulfilled" ? r.value.error : String(r.reason))
      .filter(Boolean) as string[]

    setData({
      health: parsed[0] as Record<string, unknown> | null,
      systemHealth: parsed[1] as Record<string, unknown> | null,
      runtimeTelemetry: parsed[2] as Record<string, unknown> | null,
      runtimeInfrastructure: parsed[3] as Record<string, unknown> | null,
      executiveSnapshot: parsed[4] as Record<string, unknown> | null,
      executiveAnalytics: parsed[5] as Record<string, unknown> | null,
      memoryStatus: parsed[6] as Record<string, unknown> | null,
      graphHealth: parsed[7] as Record<string, unknown> | null,
      approvalSummary: parsed[8] as Record<string, unknown> | null,
      securityStatus: parsed[9] as Record<string, unknown> | null,
      costSummary: parsed[10] as Record<string, unknown> | null,
      governanceOverview: parsed[11] as Record<string, unknown> | null,
    })
    setErrors(errs)
    setIsLoading(false)
    setLastRefresh(new Date().toISOString())
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshAll()
    const interval = setInterval(refreshAll, refreshIntervalMs)
    return () => clearInterval(interval)
  }, [refreshAll, refreshIntervalMs])

  return (
    <EnterpriseContext.Provider value={{ ...data, isLoading, lastRefresh, errors, refreshAll }}>
      {children}
    </EnterpriseContext.Provider>
  )
}