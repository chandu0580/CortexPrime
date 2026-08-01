"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { fetchDashboardRollbacks } from "@/services/dashboard/rollbacks"

export function useDashboardRollbacks() {
    const query = useQuery({
        queryKey: queryKeys.dashboard.rollbacks(),
        queryFn: fetchDashboardRollbacks,
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
