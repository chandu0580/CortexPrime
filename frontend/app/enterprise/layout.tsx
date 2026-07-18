import { ReactNode } from "react"
import EnterpriseSidebar from "./EnterpriseSidebar"

export default function EnterpriseLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-[var(--background)]">
      <EnterpriseSidebar />
      <main className="flex-1 overflow-y-auto p-6 cortex-scroll">
        {children}
      </main>
    </div>
  )
}
