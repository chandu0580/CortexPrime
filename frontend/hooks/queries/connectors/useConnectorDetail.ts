"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { getConnectorDetail } from "@/services/connector-api"

export function useConnectorDetail(connectorType: string) {
    return useQuery({
        queryKey: queryKeys.connectors.detail(connectorType),
        queryFn:  () => getConnectorDetail(connectorType),
        enabled:  !!connectorType,
    })
}
