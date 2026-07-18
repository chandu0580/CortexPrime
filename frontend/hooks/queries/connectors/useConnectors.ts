"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { listConnectors } from "@/services/connector-api"

export function useConnectors() {
    return useQuery({
        queryKey: queryKeys.connectors.list(),
        queryFn:  listConnectors,
    })
}
