"use client"
import { useState } from "react"
import { motion } from "framer-motion"
import { Terminal } from "lucide-react"
import GlassPanel from "@/components/ui/GlassPanel"
import SectionHeader from "@/components/ui/SectionHeader"
import GradientButton from "@/components/ui/GradientButton"
import { cognitionService } from "@/services/cognition"

// ==========================================
// OPERATOR CONSOLE
// ==========================================

interface ConsoleLine { text: string; type: "input" | "output" | "error" }

export default function OperatorConsole() {
    const [input, setInput]   = useState("")
    const [lines, setLines]   = useState<ConsoleLine[]>([
        { text: "CortexPrime Operator Console v3.0", type: "output" },
        { text: "Autonomous execution ready.", type: "output" },
    ])
    const [loading, setLoading] = useState(false)

    async function execute() {
        if (!input.trim()) return
        const cmd = input.trim()
        setLines((l) => [...l, { text: `> ${cmd}`, type: "input" }])
        setInput("")
        setLoading(true)
        try {
            const r = await cognitionService.executeAutonomous({ objective: cmd }) as Record<string, unknown>
            const out = String(r?.result ?? r?.status ?? JSON.stringify(r))
            setLines((l) => [...l, { text: out, type: "output" }])
        } catch (e) {
            setLines((l) => [...l, { text: `Error: ${(e as Error).message}`, type: "error" }])
        } finally {
            setLoading(false)
        }
    }

    return (
        <GlassPanel padding={false} className="flex flex-col">
            <div className="flex items-center gap-2 border-b border-[#e8f5ee] px-4 py-3">
                <Terminal size={14} style={{ color: "#82c0a4" }} />
                <SectionHeader title="Operator Console" className="mb-0" />
            </div>
            <div className="cortex-scroll flex-1 overflow-y-auto max-h-72 p-4 font-mono text-xs space-y-1">
                {lines.map((line, i) => (
                    <motion.div
                        key={i}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className={
                            line.type === "input"  ? "text-[#82c0a4]" :
                            line.type === "error"  ? "text-[#dc2626]"  :
                            "text-[#4a4a4a]"
                        }
                    >
                        {line.text}
                    </motion.div>
                ))}
            </div>
            <div className="flex gap-2 border-t border-[#e8f5ee] p-3">
                <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && execute()}
                    placeholder="Enter command..."
                    className="flex-1 rounded-lg border border-[#dceee4] bg-[#f0f7f4] px-3 py-2 text-xs text-[#4a4a4a] placeholder:text-[#a3a3a3] outline-none font-mono focus:border-[#82c0a4]/40"
                />
                <GradientButton onClick={execute} loading={loading} size="sm">Run</GradientButton>
            </div>
        </GlassPanel>
    )
}
