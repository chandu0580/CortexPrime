"use client"

import { useQuery } from "@tanstack/react-query"
import { runtimeService } from "@/services/runtime"
import { queryKeys } from "@/lib/query"

export function useRuntimeHealth() {
    return useQuery({
        queryKey: queryKeys.runtime.health(),
        queryFn:  () => runtimeService.getHealth(),
    })
}
