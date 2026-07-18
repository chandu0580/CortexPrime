"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { getConnectorHealth } from "@/services/connector-api"

export function useConnectorHealth(connectorType: string) {
    return useQuery({
        queryKey: queryKeys.connectors.health(connectorType),
        queryFn:  () => getConnectorHealth(connectorType),
        enabled:  !!connectorType,
    })
}
