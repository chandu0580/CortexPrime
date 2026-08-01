"use client";

import AuthGuard from "@/components/auth/AuthGuard";
import BrowserCenter from "@/components/browser-center/BrowserCenter";

export default function BrowserPage() {
  return (
    <AuthGuard>
      <BrowserCenter />
    </AuthGuard>
  );
}
