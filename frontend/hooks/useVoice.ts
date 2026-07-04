"use client"
import { useVoiceStore } from "@/store/voiceStore"
import { voiceService } from "@/services/voice"

// ==========================================
// USE VOICE HOOK
// ==========================================

export function useVoice() {
    const store = useVoiceStore()

    async function synthesize(text: string) {
        store.setStatus("speaking")
        try {
            await voiceService.synthesize(text, store.activeProfile)
        } finally {
            store.setStatus("idle")
        }
    }

    async function test() {
        store.setStatus("speaking")
        try {
            await voiceService.test(store.activeProfile)
        } finally {
            store.setStatus("idle")
        }
    }

    return { ...store, synthesize, test }
}
