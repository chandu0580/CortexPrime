"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { fetchDashboardBranchProtection } from "@/services/dashboard/branchProtection"

export function useDashboardBranchProtection() {
    const query = useQuery({
        queryKey: queryKeys.dashboard.branchProtection(),
        queryFn: fetchDashboardBranchProtection,
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
