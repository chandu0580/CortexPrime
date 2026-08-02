"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { fetchDashboardVulnerabilities } from "@/services/dashboard/vulnerabilities"

export function useDashboardVulnerabilities() {
    const query = useQuery({
        queryKey: queryKeys.dashboard.vulnerabilities(),
        queryFn: fetchDashboardVulnerabilities,
        refetchInterval: 15000,
    })

    return {
        data: query.data,
        isLoading: query.isLoading,
        isError: query.isError,
        error: query.error,
        isPartialFailure: query.data?.isPartialFailure ?? false,
    }
}
