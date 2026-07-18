"use client"

import { useConnectors } from "@/hooks/queries/useConnectors"
import { ConnectorGrid } from "@/components/enterprise"

export default function OperationsCenter() {
  const { data } = useConnectors()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const connectors = (data?.connectors ?? []) as any

  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="type-heading-xl text-[var(--text-primary)]">Operations Center</h1>
        <p className="type-body text-[var(--text-muted)] mt-1">Connected infrastructure and services</p>
      </div>

      <ConnectorGrid connectors={connectors} />
    </div>
  )
}
