"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { fetchDashboardDeployChecks } from "@/services/dashboard/deployChecks"

export function useDashboardDeployChecks() {
    const query = useQuery({
        queryKey: queryKeys.dashboard.deployChecks(),
        queryFn: fetchDashboardDeployChecks,
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
