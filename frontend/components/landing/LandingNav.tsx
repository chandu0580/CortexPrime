"use client"
import Link from "next/link"
import { motion } from "framer-motion"
import { Hexagon } from "lucide-react"

// ==========================================
// LANDING NAV — Premium Light
// ==========================================

const NAV_LINKS = ["Capabilities", "Architecture", "Systems", "Mission", "Pricing"]

export default function LandingNav() {
    return (
        <motion.nav
            className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-8 py-4"
            style={{
                background: "rgba(255,255,255,0.92)",
                backdropFilter: "blur(20px)",
                WebkitBackdropFilter: "blur(20px)",
                borderBottom: "1px solid rgba(226,232,240,0.8)",
                boxShadow: "0 1px 3px rgba(15,23,42,0.05)",
            }}
            initial={{ opacity: 0, y: -16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
        >
            {/* Logo */}
            <div className="flex items-center gap-2.5">
                <div className="relative flex items-center justify-center w-8 h-8">
                    <div
                        className="absolute inset-0 rounded-lg"
                        style={{ background: "linear-gradient(135deg, #82c0a4, #4a8c70)" }}
                    />
                    <Hexagon size={16} className="relative z-10 text-white" strokeWidth={2.5} />
                </div>
                <div className="flex flex-col leading-none">
                    <span className="text-sm font-black tracking-widest text-[#1a1a1a] uppercase">
                        CortexPrime
                    </span>
                    <span className="text-[9px] glyph-mono text-[#82c0a4] tracking-widest uppercase">
                        AI Operating System
                    </span>
                </div>
            </div>

            {/* Nav links */}
            <div className="hidden md:flex items-center gap-8">
                {NAV_LINKS.map(label => (
                    <a
                        key={label}
                        href={`#${label.toLowerCase()}`}
                        className="text-[15px] font-semibold text-[#4a4a4a] hover:text-[#1a1a1a] transition-colors"
                    >
                        {label}
                    </a>
                ))}
            </div>

            {/* Right side */}
            <div className="flex items-center gap-4">
                <div className="hidden sm:flex items-center gap-2 text-[15px] font-medium text-[#737373]">
                    <span className="w-2 h-2 rounded-full bg-[#4a8c70] animate-blink" />
                    System Status
                </div>
                <Link href="/login">
                    <motion.button
                        className="flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white rounded-lg"
                        style={{
                            background: "linear-gradient(135deg, #82c0a4, #4a8c70)",
                            boxShadow: "0 4px 14px rgba(130,192,164,0.35)",
                        }}
                        whileHover={{ boxShadow: "0 6px 20px rgba(130,192,164,0.45)", y: -1 }}
                        whileTap={{ scale: 0.97 }}
                    >
                        Access System →
                    </motion.button>
                </Link>
            </div>
        </motion.nav>
    )
}
