"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import Link from "next/link";
import { CircleHelp, Moon, Sun } from "lucide-react";

import BrandPanel from "@/components/auth/BrandPanel";
import LoginCard from "@/components/auth/LoginCard";
import { useAuthStore } from "@/store/authStore";

const SAVED_LOGIN_KEY = "cortexprime.savedLogin";

type SavedLogin = {
  email: string;
  password: string;
};

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginPageContent />
    </Suspense>
  );
}

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const login = useAuthStore((state) => state.login);
  const loginError = useAuthStore((state) => state.loginError);
  const clearError = useAuthStore((state) => state.clearError);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  // Demonstration prefill. Read from the environment rather than written here,
  // so a working credential never lands in the repository: these come from
  // frontend/.env.local, which .gitignore already excludes. Unset in any
  // deployment that does not want them, and the fields start empty as before.
  const [email, setEmail] = useState(
    process.env.NEXT_PUBLIC_DEMO_EMAIL ?? "",
  );
  const [password, setPassword] = useState(
    process.env.NEXT_PUBLIC_DEMO_PASSWORD ?? "",
  );
  const [rememberMe, setRememberMe] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [accessGranted, setAccessGranted] = useState(false);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void useAuthStore.getState().initFromToken();
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      try {
        const saved = window.localStorage.getItem(SAVED_LOGIN_KEY);
        if (!saved) return;

        const parsed = JSON.parse(saved) as Partial<SavedLogin>;
        // Only a remembered value that actually has something in it replaces
        // what is already in the field: an empty string saved by an earlier
        // visit would otherwise clear a prefilled credential a moment after
        // the page renders, which looks exactly like the prefill not working.
        if (typeof parsed.email === "string" && parsed.email) {
          setEmail(parsed.email);
        }
        if (typeof parsed.password === "string" && parsed.password) {
          setPassword(parsed.password);
        }
        setRememberMe(Boolean(parsed.email || parsed.password));
      } catch {
        window.localStorage.removeItem(SAVED_LOGIN_KEY);
      }
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, []);



  function handleEmailChange(value: string) {
    if (loginError) clearError();
    setEmail(value);
  }

  function handlePasswordChange(value: string) {
    if (loginError) clearError();
    setPassword(value);
  }

  function handleRememberChange(checked: boolean) {
    setRememberMe(checked);
    if (!checked) {
      window.localStorage.removeItem(SAVED_LOGIN_KEY);
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading) return;

    setLoading(true);
    const ok = await login(email, password);

    if (!ok) {
      setLoading(false);
      return;
    }

    if (rememberMe) {
      window.localStorage.setItem(
        SAVED_LOGIN_KEY,
        JSON.stringify({ email, password } satisfies SavedLogin),
      );
    } else {
      window.localStorage.removeItem(SAVED_LOGIN_KEY);
    }

    setAccessGranted(true);
    window.setTimeout(() => {
      const next = searchParams?.get("next") || "/command";
      router.push(next);
    }, 650);
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#F8FAFC] text-[#111827]">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-[-10%] top-[-14%] h-[30rem] w-[30rem] rounded-full bg-[radial-gradient(circle,rgba(56,184,138,0.08)_0%,rgba(56,184,138,0.02)_48%,transparent_74%)]" />
        <div className="absolute bottom-[-14%] right-[-10%] h-[30rem] w-[30rem] rounded-full bg-[radial-gradient(circle,rgba(110,231,183,0.10)_0%,rgba(110,231,183,0.02)_45%,transparent_74%)]" />
      </div>

      <div className="relative z-10 flex min-h-screen flex-col">
        {/* Top-right bar: Light/Dark toggle + Need help */}
        <div className="flex justify-end px-6 pt-5 sm:px-8 lg:px-10">
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="flex items-center gap-3"
          >
            {/* Theme toggle — sun/moon pill */}
            <div className="flex items-center rounded-full border border-[#E5E7EB] bg-white/88 p-1 shadow-[0_4px_12px_rgba(148,163,184,0.1)] backdrop-blur">
              <button
                type="button"
                aria-label="Light mode"
                className="flex h-8 w-8 items-center justify-center rounded-full bg-[#F9FAFB] text-[#374151] shadow-sm transition hover:bg-white"
              >
                <Sun className="h-4 w-4" />
              </button>
              <button
                type="button"
                aria-label="Dark mode"
                className="flex h-8 w-8 items-center justify-center rounded-full text-[#9CA3AF] transition hover:text-[#374151]"
              >
                <Moon className="h-4 w-4" />
              </button>
            </div>

            {/* Need help */}
            <div className="flex items-center gap-2 rounded-full border border-[#E5E7EB] bg-white/88 px-4 py-2 text-[0.9rem] font-medium text-[#6B7280] shadow-[0_4px_12px_rgba(148,163,184,0.08)] backdrop-blur">
              <Link href="/#resources" className="transition hover:text-[#111827]">
                Need help?
              </Link>
              <CircleHelp className="h-4 w-4 text-[#38B88A]" />
            </div>
          </motion.div>
        </div>

        {/* Two-column grid */}
        <div className="flex flex-1 flex-col lg:grid lg:grid-cols-[1.08fr_0.92fr] lg:pt-2">
          <BrandPanel />

          <section className="flex items-center justify-center px-6 py-10 sm:px-8 lg:px-10 lg:py-12">
            <LoginCard
              email={email}
              password={password}
              rememberMe={rememberMe}
              showPassword={showPassword}
              loading={loading}
              error={loginError}
              accessGranted={accessGranted}
              onEmailChange={handleEmailChange}
              onPasswordChange={handlePasswordChange}
              onRememberChange={handleRememberChange}
              onTogglePassword={() => setShowPassword((current) => !current)}
              onSubmit={handleSubmit}
            />
          </section>
        </div>

        <footer className="px-6 pb-5 text-center text-[0.88rem] text-[#9CA3AF] sm:px-8 lg:px-10">
          <p>© 2025 CortexPrime. All rights reserved.</p>
        </footer>
      </div>
    </div>
  );
}

