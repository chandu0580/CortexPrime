"use client";

import AuthGuard from "@/components/auth/AuthGuard";
import SettingsCenter from "@/components/settings-center/SettingsCenter";

export default function SettingsPage() {
  return (
    <AuthGuard>
      <SettingsCenter />
    </AuthGuard>
  );
}