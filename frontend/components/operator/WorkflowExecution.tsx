"use client"
import { useState } from "react"
import { motion } from "framer-motion"
import { Play, List } from "lucide-react"
import GlassPanel from "@/components/ui/GlassPanel"
import SectionHeader from "@/components/ui/SectionHeader"
import GradientButton from "@/components/ui/GradientButton"
import { api } from "@/services/api"

// ==========================================
// WORKFLOW EXECUTION
// ==========================================

export default function WorkflowExecution() {
    const [goal, setGoal]       = useState("")
    const [loading, setLoading] = useState(false)
    const [result, setResult]   = useState<string | null>(null)

    async function runWorkflow() {
        if (!goal.trim()) return
        setLoading(true)
        setResult(null)
        try {
            const r = await api.post<{ result?: string }>("/computer/execute-workflow", { goal }) as Record<string, unknown>
            setResult(String(r?.result ?? r?.status ?? "Workflow queued"))
        } catch (e) {
            setResult(`Error: ${(e as Error).message}`)
        } finally {
            setLoading(false)
        }
    }

    return (
        <GlassPanel>
            <SectionHeader title="Workflow Execution" subtitle="Autonomous task automation" />
            <div className="flex flex-col gap-3">
                <textarea
                    rows={3}
                    value={goal}
                    onChange={(e) => setGoal(e.target.value)}
                    placeholder="Describe the workflow goal..."
                    className="w-full resize-none rounded-lg border border-[#dceee4] bg-[#f0f7f4] px-3 py-2.5 text-xs text-[#4a4a4a] placeholder:text-[#a3a3a3] outline-none focus:border-[#82c0a4]/40"
                />
                <GradientButton onClick={runWorkflow} loading={loading} size="sm">
                    <Play size={13} /> Execute Workflow
                </GradientButton>
                {result && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="rounded-lg border border-[#dceee4] bg-[#f0f7f4] p-3 text-xs text-[#737373]"
                    >
                        {result}
                    </motion.div>
                )}
            </div>
        </GlassPanel>
    )
}
