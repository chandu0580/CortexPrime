"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Eye, EyeOff, Lock, Mail, TriangleAlert } from "lucide-react";
import Link from "next/link";
import type { FormEvent } from "react";

import Button from "@/components/ui/Button";
import Checkbox from "@/components/ui/Checkbox";
import Input from "@/components/ui/Input";

type LoginFormProps = {
  email: string;
  password: string;
  rememberMe: boolean;
  showPassword: boolean;
  loading: boolean;
  error: string | null;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onRememberChange: (checked: boolean) => void;
  onTogglePassword: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => Promise<void>;
};

export default function LoginForm({
  email,
  password,
  rememberMe,
  showPassword,
  loading,
  error,
  onEmailChange,
  onPasswordChange,
  onRememberChange,
  onTogglePassword,
  onSubmit,
}: LoginFormProps) {
  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <Input
        label="Email or Username"
        type="text"
        value={email}
        onChange={(event) => onEmailChange(event.target.value)}
        autoComplete="username"
        placeholder="Enter your email or username"
        leftAdornment={<Mail className="h-4 w-4" />}
        aria-label="Email or username"
        required
      />

      <Input
        label="Password"
        type={showPassword ? "text" : "password"}
        value={password}
        onChange={(event) => onPasswordChange(event.target.value)}
        autoComplete="current-password"
        placeholder="Enter your password"
        leftAdornment={<Lock className="h-4 w-4" />}
        rightAdornment={
          <button
            type="button"
            onClick={onTogglePassword}
            className="rounded-full p-1 text-[#9CA3AF] transition hover:text-[#6B7280] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#B7E5D3]"
            aria-label={showPassword ? "Hide password" : "Show password"}
          >
            {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        }
        required
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Checkbox
          label="Remember Me"
          checked={rememberMe}
          onChange={(event) => onRememberChange(event.target.checked)}
        />
        <Link
          href="/#resources"
          className="text-[0.94rem] font-semibold text-[#38B88A] transition hover:text-[#2F9F77] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#B7E5D3]"
        >
          Forgot password?
        </Link>
      </div>

      <AnimatePresence>
        {error ? (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="flex items-start gap-3 rounded-[18px] border border-[#FBD5D5] bg-[#FEF2F2] px-4 py-3 text-[0.92rem] font-medium text-[#B91C1C]"
            role="alert"
          >
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <Button
        type="submit"
        loading={loading}
        rightIcon={<ArrowRight className="h-4 w-4" aria-hidden="true" />}
      >
        Sign in to CortexPrime
      </Button>
    </form>
  );
}
