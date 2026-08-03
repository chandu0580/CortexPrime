"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { fetchDashboardDockerHealth } from "@/services/dashboard/dockerHealth"

export function useDashboardDockerHealth() {
    const query = useQuery({
        queryKey: queryKeys.dashboard.dockerHealth(),
        queryFn: fetchDashboardDockerHealth,
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
