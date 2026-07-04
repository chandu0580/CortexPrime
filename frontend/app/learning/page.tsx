"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { MissionControlShell } from "@/components/mission-control/MissionControlShell";
import { useAuthStore } from "@/store/authStore";

export default function LearningPage() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login?next=%2Flearning");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  return <MissionControlShell initialWorkspace="learning" />;
}
