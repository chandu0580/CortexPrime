"use client";

import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { ease } from "@/lib/motion-tokens";
import { cn } from "@/utils/cn";

type ButtonProps = Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  "onDrag" | "onDragStart" | "onDragEnd" | "onAnimationStart"
> & {
  variant?: "primary" | "secondary" | "ghost";
  size?: "md" | "lg";
  loading?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
};

export default function Button({
  variant = "primary",
  size = "lg",
  loading = false,
  disabled,
  leftIcon,
  rightIcon,
  className,
  children,
  type = "button",
  ...props
}: ButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <motion.button
      type={type}
      whileHover={isDisabled ? undefined : { y: -2, scale: 1.01 }}
      whileTap={isDisabled ? undefined : { scale: 0.985 }}
      transition={{ duration: 0.2, ease: ease.out }}
      disabled={isDisabled}
      className={cn(
        "inline-flex w-full items-center justify-center gap-2 rounded-[18px] border font-semibold tracking-[-0.02em] transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#B7E5D3] focus-visible:ring-offset-2 focus-visible:ring-offset-white disabled:cursor-not-allowed disabled:opacity-70",
        size === "lg" ? "h-14 px-6 text-[1rem]" : "h-11 px-4 text-[0.94rem]",
        variant === "primary" &&
          "border-[#38B88A] bg-[#38B88A] text-white shadow-[0_12px_30px_rgba(56,184,138,0.24)] hover:border-[#2F9F77] hover:bg-[#2F9F77]",
        variant === "secondary" &&
          "border-[#E5E7EB] bg-white text-[#111827] shadow-[0_10px_24px_rgba(15,23,42,0.06)] hover:border-[#D1D5DB] hover:bg-[#F9FAFB]",
        variant === "ghost" &&
          "border-transparent bg-transparent text-[#6B7280] shadow-none hover:text-[#111827]",
        className,
      )}
      {...props}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : leftIcon}
      <span>{children}</span>
      {!loading ? rightIcon : null}
    </motion.button>
  );
}
