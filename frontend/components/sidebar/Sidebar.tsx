"use client"

import Link from "next/link"

import { usePathname } from "next/navigation"

import {

    LayoutDashboard,

    Brain,

    Database,

    BarChart3,

    ShieldCheck,

    Settings,

    FolderOpen

} from "lucide-react"


// ==========================================
// MENU ITEMS
// ==========================================

const menuItems = [

    {
        icon: LayoutDashboard,
        label: "Dashboard",
        href: "/"
    },

    {
        icon: Brain,
        label: "Runtime",
        href: "/runtime"
    },

    {
        icon: Database,
        label: "Memory",
        href: "/memory"
    },

    {
        icon: FolderOpen,
        label: "Workspace",
        href: "/workspace"
    },

    {
        icon: BarChart3,
        label: "Analytics",
        href: "/analytics"
    },

    {
        icon: ShieldCheck,
        label: "Governance",
        href: "/governance"
    },

    {
        icon: Settings,
        label: "Settings",
        href: "/settings"
    },
    {
        icon: LayoutDashboard,
        label: "Enterprise Platform",
        href: "/enterprise"
    }
]


// ==========================================
// COMPONENT
// ==========================================

export default function Sidebar() {

    const pathname =
        usePathname()

    return (

        <aside
            className="w-[260px] h-screen bg-white border-r p-6 flex flex-col"
        >

            {/* LOGO */}

            <div
                className="text-2xl font-bold mb-10"
            >

                🧠 CortexPrime

            </div>

            {/* MENU */}

            <nav
                className="space-y-3"
            >

                {

                    menuItems.map(

                        (
                            item
                        ) => {

                            const Icon =
                                item.icon

                            const isActive =

                                pathname ===
                                item.href

                            return (

                                <Link

                                    key={
                                        item.label
                                    }

                                    href={
                                        item.href
                                    }

                                    className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                                        isActive
                                            ? "bg-black text-white"
                                            : "hover:bg-gray-100"
                                    }`}
                                >

                                    <Icon
                                        size={20}
                                    />

                                    <span>

                                        {
                                            item.label
                                        }

                                    </span>

                                </Link>
                            )
                        }
                    )
                }

            </nav>

        </aside>
    )
}