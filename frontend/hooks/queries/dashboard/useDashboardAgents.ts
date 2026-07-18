"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { fetchDashboardAgents } from "@/services/dashboard/agents"

export function useDashboardAgents() {
    const query = useQuery({
        queryKey: queryKeys.dashboard.agents(),
        queryFn: fetchDashboardAgents,
    })

    return {
        data: query.data,
        isLoading: query.isLoading,
        isError: query.isError,
        error: query.error,
        isPartialFailure: query.data?.isPartialFailure ?? false,
    }
}
