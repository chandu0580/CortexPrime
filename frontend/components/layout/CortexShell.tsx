"use client"
import { useCognition } from "@/hooks/useCognition"
import CortexSidebar from "./CortexSidebar"
import CortexNavbar  from "./CortexNavbar"
import AnimatedGrid  from "@/components/ui/AnimatedGrid"
import AuthGuard     from "@/components/auth/AuthGuard"
import ExecutiveCommandStrip from "./ExecutiveCommandStrip"

// ==========================================
// CORTEX SHELL
// ==========================================

interface CortexShellProps {
    children:  React.ReactNode
    title?:    string
    subtitle?: string
}

export default function CortexShell({ children, title, subtitle }: CortexShellProps) {
    useCognition()

    return (
        <AuthGuard>
            <div className="flex min-h-screen" style={{ background: "var(--background)" }}>
                <CortexSidebar />
                <div className="relative flex flex-1 flex-col pl-16 lg:pl-52">
                    <AnimatedGrid />
                    <CortexNavbar title={title} subtitle={subtitle} />
                    <ExecutiveCommandStrip />
                    <main className="relative z-10 flex-1 overflow-auto p-5">
                        {children}
                    </main>
                </div>
            </div>
        </AuthGuard>
    )
}

