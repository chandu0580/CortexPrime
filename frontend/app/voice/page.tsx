"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import VoiceRuntime from "@/components/voice-runtime/VoiceRuntime";
import { useAuthStore } from "@/store/authStore";

export default function VoicePage() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login?next=%2Fvoice");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  return <VoiceRuntime />;
}
