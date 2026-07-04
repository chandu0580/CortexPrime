"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { fetchDashboardHeader } from "@/services/dashboard/header"

export function useDashboardHeader() {
    const query = useQuery({
        queryKey: queryKeys.dashboard.header(),
        queryFn: fetchDashboardHeader,
        refetchInterval: 15_000,
    })

    return {
        data: query.data,
        isLoading: query.isLoading,
        isError: query.isError,
        error: query.error,
        isPartialFailure: query.data?.isPartialFailure ?? false,
    }
}
