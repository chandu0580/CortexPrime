"use client"
import { motion } from "framer-motion"
import { Globe } from "lucide-react"
import GlassPanel from "@/components/ui/GlassPanel"
import SectionHeader from "@/components/ui/SectionHeader"
import StatusPill from "@/components/ui/StatusPill"

// ==========================================
// BROWSER RUNTIME
// ==========================================

export default function BrowserRuntime() {
    return (
        <GlassPanel>
            <SectionHeader title="Browser Runtime" subtitle="Autonomous web execution" accent />
            <div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
                <motion.div
                    animate={{ y: [0, -4, 0] }}
                    transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
                    className="flex h-14 w-14 items-center justify-center rounded-full border border-[#82c0a4]/30 bg-[#82c0a4]/8"
                >
                    <Globe size={26} style={{ color: "#82c0a4" }} />
                </motion.div>
                <StatusPill label="Ready" variant="success" />
                <p className="text-xs text-[#737373]">Browser automation available via computer-use tools</p>
            </div>
        </GlassPanel>
    )
}
