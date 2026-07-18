"use client"

import { useRuntimeStatus } from "@/hooks/queries/useAgents"
import { useConnectors } from "@/hooks/queries/useConnectors"
import { Badge } from "@/components/enterprise/ui"
import { TopologyGraph, DefaultTopologyNodes, defaultConnections } from "@/components/enterprise"

export default function DigitalTwinPage() {
  const { data: runtimeStatus } = useRuntimeStatus()
  const { data: connectorsData } = useConnectors()
  const connectors = connectorsData?.connectors ?? []

  const nodes = DefaultTopologyNodes(runtimeStatus ?? {})
  const connections = defaultConnections

  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="type-heading-xl text-[var(--text-primary)]">Digital Twin</h1>
        <p className="type-body text-[var(--text-muted)] mt-1">Infrastructure topology and system simulation</p>
      </div>

      <TopologyGraph nodes={nodes} connections={connections} />

      <div className="surface-panel p-5">
        <h2 className="type-heading-sm text-[var(--text-primary)] mb-4">Connected Services</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {connectors.length > 0 ? (
            connectors.map((c) => (
              <div key={c.connector_type} className="p-3 rounded-xl bg-[var(--surface-raised)]">
                <p className="type-body-sm text-[var(--text-primary)]">{c.name || c.connector_type}</p>
                <Badge variant={c.status === "connected" || c.status === "active" ? "success" : "default"}>
                  {c.status}
                </Badge>
              </div>
            ))
          ) : (
            <>
              {["GitHub", "Docker", "Kubernetes", "Prometheus"].map((name) => (
                <div key={name} className="p-3 rounded-xl bg-[var(--surface-raised)]">
                  <p className="type-body-sm text-[var(--text-primary)]">{name}</p>
                  <Badge variant="default">Not connected</Badge>
                </div>
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
