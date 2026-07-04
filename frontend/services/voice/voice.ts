import { api } from "../api"
import type { VoiceProfile } from "@/types/voice"

// ==========================================
// VOICE SERVICE
// ==========================================

export const voiceService = {
    listProfiles: () =>
        api.get<{ profiles: VoiceProfile[] }>("/voice/profiles"),

    setProfile: (profileId: string) =>
        api.post("/voice/set-profile", { profile_id: profileId }),

    synthesize: (text: string, profileId?: string) =>
        api.post("/voice/synthesize", { text, profile_id: profileId }),

    test: (profileId?: string) =>
        api.post("/voice/test", { profile_id: profileId }),
}
