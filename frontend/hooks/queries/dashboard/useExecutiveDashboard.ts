"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { fetchExecutiveDashboard } from "@/services/dashboard/executive"

export function useExecutiveDashboard() {
    return useQuery({
        queryKey: queryKeys.executiveDashboard.data(),
        queryFn:  fetchExecutiveDashboard,
    })
}
