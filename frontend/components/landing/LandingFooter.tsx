"use client"
import Link from "next/link"
import { motion } from "framer-motion"
import { Hexagon, ExternalLink, Shield } from "lucide-react"
import { apiUrl } from "@/lib/constants"

// ==========================================
// NAV LINKS
// ==========================================

const NAV_GROUPS = [
    {
        heading: "System",
        links: [
            { label: "Runtime",    href: "/runtime"    },
            { label: "Cognition",  href: "/cognition"  },
            { label: "Memory",     href: "/memory"     },
            { label: "Operator",   href: "/operator"   },
        ],
    },
    {
        heading: "Interface",
        links: [
            { label: "Voice",      href: "/voice"      },
            { label: "Analytics",  href: "/analytics"  },
            { label: "Governance", href: "/governance" },
            { label: "Settings",   href: "/settings"   },
        ],
    },
    {
        heading: "Resources",
        links: [
            { label: "API Docs",     href: apiUrl("/docs"), ext: true },
            { label: "Architecture", href: "#architecture" },
            { label: "Agent Mesh",   href: "#agents"       },
            { label: "Capabilities", href: "#capabilities" },
        ],
    },
]

const STATUS_ITEMS = [
    { label: "Cognitive Engine", status: "Nominal",  color: "#4a8c70" },
    { label: "Agent Mesh",       status: "Active",   color: "#4a8c70" },
    { label: "Memory Fabric",    status: "Synced",   color: "#82c0a4" },
    { label: "Event Bus",        status: "Live",     color: "#4a8c70" },
]

// ==========================================
// FOOTER — Premium Light
// ==========================================

export default function LandingFooter() {
    return (
        <footer
            className="relative overflow-hidden"
            style={{ background: "#ffffff", borderTop: "1px solid #dceee4" }}
        >
            <div className="relative z-10 max-w-6xl mx-auto px-8">
                <div className="pt-16 pb-12 grid grid-cols-1 lg:grid-cols-4 gap-12">

                    {/* Brand column */}
                    <div className="flex flex-col gap-5">
                        <div className="flex items-center gap-2.5">
                            <div className="flex items-center justify-center w-9 h-9 rounded-lg" style={{ background: "linear-gradient(135deg, #82c0a4, #4a8c70)" }}>
                                <Hexagon size={18} className="text-white" strokeWidth={2.5} />
                            </div>
                            <div>
                                <div className="text-sm font-black tracking-widest text-[#1a1a1a]">CORTEXPRIME</div>
                                <div className="text-[9px] glyph-mono text-[#82c0a4] tracking-widest">AI Operating System</div>
                            </div>
                        </div>

                        <p className="text-xs text-[#737373] leading-relaxed max-w-xs">
                            An elite autonomous cognitive operating system with multi-agent
                            orchestration, persistent memory, and real-time cognition.
                        </p>

                        <div className="flex flex-col gap-2">
                            {STATUS_ITEMS.map(({ label, status, color }) => (
                                <div key={label} className="flex items-center justify-between">
                                    <span className="text-[10px] text-[#a3a3a3]">{label}</span>
                                    <div className="flex items-center gap-1.5">
                                        <div className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
                                        <span className="text-[10px] font-semibold" style={{ color }}>{status}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Nav groups */}
                    {NAV_GROUPS.map(group => (
                        <div key={group.heading} className="flex flex-col gap-4">
                            <div className="text-xs font-bold tracking-widest text-[#82c0a4] uppercase">{group.heading}</div>
                            <div className="flex flex-col gap-2.5">
                                {group.links.map(({ label, href, ext }: any) =>
                                    ext ? (
                                        <a key={label} href={href} target="_blank" rel="noopener noreferrer"
                                            className="flex items-center gap-1 text-sm text-[#737373] hover:text-[#1a1a1a] transition-colors">
                                            {label} <ExternalLink size={10} />
                                        </a>
                                    ) : (
                                        <Link key={label} href={href}
                                            className="text-sm text-[#737373] hover:text-[#1a1a1a] transition-colors">
                                            {label}
                                        </Link>
                                    )
                                )}
                            </div>
                        </div>
                    ))}
                </div>

                <div className="h-px bg-[#e8f5ee]" />

                <div className="py-6 flex flex-col md:flex-row items-center justify-between gap-4">
                    <div className="flex items-center gap-2 text-xs text-[#a3a3a3]">
                        <Shield size={11} />
                        Clearance Level 5 — All access monitored
                    </div>
                    <div className="text-xs text-[#a3a3a3]">
                        © 2026 CortexPrime Systems — Runtime v3.0.0
                    </div>
                </div>
            </div>
        </footer>
    )
}

