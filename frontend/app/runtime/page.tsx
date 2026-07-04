"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import RuntimeCenter from "@/components/runtime-center/RuntimeCenter";
import { useAuthStore } from "@/store/authStore";

export default function RuntimePage() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login?next=%2Fruntime");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  return <RuntimeCenter />;
}