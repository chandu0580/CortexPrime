"use client";

import AuthGuard from "@/components/auth/AuthGuard";
import VoiceRuntime from "@/components/voice-runtime/VoiceRuntime";

export default function VoicePage() {
  return (
    <AuthGuard>
      <VoiceRuntime />
    </AuthGuard>
  );
}
