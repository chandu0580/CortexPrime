"use client"

import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api-client"
import type { ConnectorInfo } from "@/types/enterprise"

export function useConnectors() {
  return useQuery<{ connectors: ConnectorInfo[]; total: number }>({
    queryKey: ["connectors"],
    queryFn: () => api.get("/api/connector/list").then((r) => r.data),
    refetchInterval: 30_000,
  })
}

export function useConnectorCapabilities(connectorType: string) {
  return useQuery<string[]>({
    queryKey: ["connector-capabilities", connectorType],
    queryFn: () => api.get(`/api/connector/${connectorType}/capabilities`).then((r) => r.data),
    enabled: !!connectorType,
  })
}
