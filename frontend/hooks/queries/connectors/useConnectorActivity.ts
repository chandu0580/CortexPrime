"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { getConnectorActivity } from "@/services/connector-api"

export function useConnectorActivity(connectorType: string, page = 1, pageSize = 20) {
    return useQuery({
        queryKey: [...queryKeys.connectors.activity(connectorType), page, pageSize] as const,
        queryFn:  () => getConnectorActivity(connectorType, page, pageSize),
        enabled:  !!connectorType,
    })
}
