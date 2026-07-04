"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, CheckCircle2, Key, ShieldCheck } from "lucide-react";
import type { FormEvent } from "react";

import LandingLogo from "@/components/landing/enterprise/LandingLogo";
import LoginForm from "@/components/auth/LoginForm";
import Card from "@/components/ui/Card";
import { variants } from "@/lib/motion-tokens";

type LoginCardProps = {
  email: string;
  password: string;
  rememberMe: boolean;
  showPassword: boolean;
  loading: boolean;
  error: string | null;
  accessGranted: boolean;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onRememberChange: (checked: boolean) => void;
  onTogglePassword: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => Promise<void>;
};

export default function LoginCard({
  email,
  password,
  rememberMe,
  showPassword,
  loading,
  error,
  accessGranted,
  onEmailChange,
  onPasswordChange,
  onRememberChange,
  onTogglePassword,
  onSubmit,
}: LoginCardProps) {
  return (
    <>
      {/* Access granted overlay */}
      <AnimatePresence>
        {accessGranted ? (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center bg-white/82 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.92, y: 18 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.92 }}
              className="rounded-[28px] border border-[#E5E7EB] bg-white px-8 py-7 text-center shadow-[0_22px_60px_rgba(148,163,184,0.18)]"
            >
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[#ECFBF4] text-[#38B88A]">
                <CheckCircle2 className="h-8 w-8" />
              </div>
              <p className="mt-5 text-[1.28rem] font-semibold tracking-[-0.04em] text-[#111827]">
                Access Granted
              </p>
              <p className="mt-2 text-[0.96rem] text-[#6B7280]">
                Initializing your enterprise workspace...
              </p>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <motion.div
        initial="hidden"
        animate="visible"
        variants={variants.fadeUp}
        className="w-full max-w-[440px]"
      >
        <Card className="rounded-[28px] border border-[#E5E7EB] bg-white px-7 py-8 shadow-[0_20px_52px_rgba(148,163,184,0.14)] sm:px-8 sm:py-9">

          {/* Logo icon */}
          <div className="flex h-14 w-14 items-center justify-center rounded-[18px] border border-[#E5E7EB] bg-[#FCFDFC] shadow-[0_8px_20px_rgba(148,163,184,0.09)]">
            <LandingLogo compact className="gap-0" textClassName="hidden" />
          </div>

          {/* Heading — matches reference exactly */}
          <div className="mt-6">
            <h1
              className="text-[1.9rem] font-bold tracking-[-0.05em]"
              style={{ color: "#111827" }}
            >
              Welcome back
            </h1>
            <p className="mt-1.5 text-[0.95rem] text-[#6B7280]">
              Sign in to your CortexPrime account
            </p>
          </div>

          {/* Form */}
          <div className="mt-7">
            <LoginForm
              email={email}
              password={password}
              rememberMe={rememberMe}
              showPassword={showPassword}
              loading={loading}
              error={error}
              onEmailChange={onEmailChange}
              onPasswordChange={onPasswordChange}
              onRememberChange={onRememberChange}
              onTogglePassword={onTogglePassword}
              onSubmit={onSubmit}
            />
          </div>

          {/* Divider */}
          <div className="my-6 flex items-center gap-3">
            <div className="h-px flex-1 bg-[#E5E7EB]" />
            <span className="text-[0.86rem] text-[#9CA3AF]">or</span>
            <div className="h-px flex-1 bg-[#E5E7EB]" />
          </div>

          {/* SSO Button — matches reference */}
          <button
            type="button"
            className="flex w-full items-center justify-center gap-2.5 rounded-[14px] border border-[#E5E7EB] bg-white py-3.5 text-[0.95rem] font-semibold text-[#374151] shadow-[0_2px_6px_rgba(15,23,42,0.06)] transition hover:bg-[#F9FAFB] hover:border-[#D1D5DB] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#B7E5D3]"
          >
            <Key className="h-4 w-4 text-[#6B7280]" aria-hidden />
            Sign in with SSO
          </button>

          {/* Security notice — matches reference */}
          <div className="mt-6 text-center">
            <div className="flex items-center justify-center gap-1.5 text-[0.82rem] text-[#9CA3AF]">
              <ShieldCheck className="h-3.5 w-3.5 text-[#38B88A]" aria-hidden />
              <span>Your data is protected with enterprise-grade security</span>
            </div>
            <p className="mt-1.5 text-[0.78rem] text-[#9CA3AF]">
              SOC 2 Ready&nbsp;•&nbsp;GDPR Compliant&nbsp;•&nbsp;ISO 27001
            </p>
          </div>
        </Card>
      </motion.div>
    </>
  );
}
