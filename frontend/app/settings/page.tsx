"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import SettingsCenter from "@/components/settings-center/SettingsCenter";
import { useAuthStore } from "@/store/authStore";

export default function SettingsPage() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login?next=%2Fsettings");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  return <SettingsCenter />;
}