"use client"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { motion } from "framer-motion"
import {
    Cpu, Users, Brain, Database, BarChart2, Mic, Settings, Zap, LogOut, FolderOpen, PlayCircle, Search, Shield, LayoutDashboard, Sparkles, Activity, DollarSign, Plug, Rocket, Radio, Box, FileCode, GitBranch, GitPullRequest, GitMerge, Building2, BrainCircuit, GitBranch as Github, Layers, Server, AlertTriangle, Target, ListRestart, MessageSquare,
} from "lucide-react"
import { useAuthStore } from "@/store/authStore"
import { cn } from "@/utils/cn"
import ThemeToggle from "@/components/theme/ThemeToggle"

// ==========================================
// NAV ITEMS
// ==========================================

interface NavSection {
    label: string
    items: { href: string; label: string; icon: React.ComponentType<{ size?: number; className?: string }> }[]
}

const navSections: NavSection[] = [
    {
        label: "Main",
        items: [
            { href: "/",                   label: "Home",         icon: LayoutDashboard },
            { href: "/executive",         label: "Executive",    icon: Cpu             },
            { href: "/digital-twin",      label: "Digital Twin", icon: Box             },
            { href: "/missions",          label: "Missions",     icon: Target          },
            { href: "/agents",            label: "Agents",       icon: Users           },
            { href: "/memory-explorer",   label: "Knowledge",    icon: Brain           },
            { href: "/chat",              label: "AI Chat",      icon: MessageSquare   },
            { href: "/replay",            label: "Replay",       icon: ListRestart     },
        ],
    },
    {
        label: "Operations",
        items: [
            { href: "/operations-center", label: "Operations",   icon: Activity        },
            { href: "/governance-center", label: "Governance",   icon: Shield          },
            { href: "/settings",          label: "Settings",     icon: Settings        },
        ],
    },
    {
        label: "Platform",
        items: [
            { href: "/enterprise-engineering-executive", label: "Engineering Executive", icon: BrainCircuit },
            { href: "/enterprise-architecture", label: "Architecture", icon: Building2      },
            { href: "/enterprise-execution",    label: "Execution",    icon: Zap            },
            { href: "/enterprise-pipeline",     label: "Pipeline",     icon: GitMerge       },
            { href: "/enterprise-git",          label: "Git Ops",      icon: GitPullRequest },
            { href: "/enterprise-patches",      label: "Patches",      icon: GitBranch      },
            { href: "/code-intelligence",       label: "Code Intel",   icon: FileCode       },
            { href: "/enterprise-github",       label: "GitHub",       icon: Github         },
            { href: "/enterprise-cicd",         label: "CI/CD",        icon: Layers         },
            { href: "/enterprise-infrastructure", label: "Infrastructure", icon: Server      },
            { href: "/enterprise-rca",           label: "RCA",          icon: AlertTriangle  },
            { href: "/enterprise-sandbox",      label: "Sandbox",      icon: Box            },
            { href: "/autonomous-runtime",      label: "Auto Run",     icon: Radio          },
            { href: "/enterprise-delivery",     label: "Delivery",     icon: Rocket         },
            { href: "/enterprise-cognition",    label: "Cognition",    icon: BrainCircuit   },
        ],
    },
    {
        label: "Admin",
        items: [
            { href: "/settings/autonomy",  label: "Autonomy Settings", icon: Settings },
            { href: "/settings/retention", label: "Data Retention",    icon: Database },
        ],
    },
]

// ==========================================
// CORTEX SIDEBAR
// ==========================================

export default function CortexSidebar() {
    const pathname = usePathname()
    const router   = useRouter()
    const { logout, user } = useAuthStore()

    function handleLogout() {
        logout()
        router.push("/")
    }

    return (
        <aside
            className="fixed left-0 top-0 z-40 flex h-screen w-16 flex-col items-center py-4 lg:w-52"
            style={{
                background:   "var(--surface)",
                borderRight:  "1px solid var(--border)",
                boxShadow:    "1px 0 0 var(--border)",
            }}
        >
            {/* Logo */}
            <div className="mb-6 flex flex-col items-center gap-1 px-3">
                <div
                    className="flex items-center justify-center w-8 h-8 mb-1 rounded-lg"
                    style={{ background: "var(--accent-primary)" }}
                >
                    <Cpu size={14} style={{ color: "var(--text-inverse)" }} />
                </div>
                <span style={{ fontSize: "var(--font-size-nav)", fontWeight: 700, letterSpacing: "-0.01em", color: "var(--text-primary)" }} className="hidden lg:block">
                    CortexPrime
                </span>
            </div>

            {/* Nav */}
            <nav className="flex w-full flex-1 flex-col gap-1 px-2 overflow-y-auto" aria-label="Main navigation">
                {navSections.map((section) => (
                    <div key={section.label} className="mb-1">
                        <span
                            className="hidden lg:block px-3 py-1 text-xs font-semibold uppercase tracking-wider"
                            style={{ color: "var(--text-muted)", fontSize: "var(--font-size-xs)" }}
                        >
                            {section.label}
                        </span>
                        {section.items.map(({ href, label, icon: Icon }) => {
                            const active = pathname === href || (href !== "/" && pathname.startsWith(href))
                            return (
                                <Link key={href} href={href}>
                                    <motion.div
                                        whileHover={{ x: 1 }}
                                        className="flex items-center gap-3 px-3 py-2 rounded-lg"
                                        style={{
                                            color:      active ? "var(--accent-primary)" : "var(--text-secondary)",
                                            background: active ? "var(--accent-muted)"   : "transparent",
                                            border:     active ? "1px solid var(--accent-border)" : "1px solid transparent",
                                            transition: "color 0.15s, background 0.15s, border-color 0.15s",
                                        }}
                                        onMouseEnter={(e) => {
                                            if (!active) (e.currentTarget as HTMLElement).style.color = "var(--text-primary)";
                                        }}
                                        onMouseLeave={(e) => {
                                            if (!active) (e.currentTarget as HTMLElement).style.color = "var(--text-secondary)";
                                        }}
                                    >
                                        <Icon size={16} className="shrink-0" />
                                        <span style={{ fontSize: "var(--font-size-nav)", fontWeight: 600, letterSpacing: "-0.005em" }} className="hidden lg:block">
                                            {label}
                                        </span>
                                        {active && (
                                            <div
                                                className="ml-auto w-1.5 h-1.5 rounded-full hidden lg:block"
                                                style={{ background: "var(--accent-primary)" }}
                                            />
                                        )}
                                    </motion.div>
                                </Link>
                            )
                        })}
                    </div>
                ))}
            </nav>

            {/* Theme + Logout */}
            <div className="flex flex-col gap-1 w-full px-2">
                {/* Theme toggle — full label on desktop */}
                <div className="px-1 hidden lg:flex">
                    <ThemeToggle variant="full" />
                </div>
                {/* Compact toggle on mobile sidebar */}
                <div className="flex justify-center lg:hidden">
                    <ThemeToggle variant="compact" />
                </div>

                <button
                    onClick={handleLogout}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg w-full mt-1"
                    style={{
                        fontSize:   "var(--font-size-nav)",
                        fontWeight: 600,
                        color:      "var(--text-muted)",
                        background: "transparent",
                        border:     "none",
                        cursor:     "pointer",
                        transition: "color 0.15s, background 0.15s",
                    }}
                    onMouseEnter={(e) => {
                        (e.currentTarget as HTMLElement).style.color = "var(--danger)";
                        (e.currentTarget as HTMLElement).style.background = "var(--danger-muted)";
                    }}
                    onMouseLeave={(e) => {
                        (e.currentTarget as HTMLElement).style.color = "var(--text-muted)";
                        (e.currentTarget as HTMLElement).style.background = "transparent";
                    }}
                >
                    <LogOut size={16} className="shrink-0" />
                    <span className="hidden lg:block">Logout</span>
                </button>
            </div>
        </aside>
    )
}
