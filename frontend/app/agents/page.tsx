"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import AgentsCenter from "@/components/agents-center/AgentsCenter";
import { useAuthStore } from "@/store/authStore";

export default function AgentsPage() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login?next=%2Fagents");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  return <AgentsCenter />;
}