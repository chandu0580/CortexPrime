"use client"
import { useCognitionStore } from "@/store/cognitionStore"
import MarkdownRenderer from "./MarkdownRenderer"
import GlassPanel from "@/components/ui/GlassPanel"
import SectionHeader from "@/components/ui/SectionHeader"

// ==========================================
// STREAMING RESPONSE
// ==========================================

export default function StreamingResponse() {
    const { streamBuffer, isStreaming } = useCognitionStore()

    if (!streamBuffer) return null

    return (
        <GlassPanel>
            <SectionHeader title="Live Response" />
            <MarkdownRenderer content={streamBuffer} streaming={isStreaming} />
        </GlassPanel>
    )
}
