"use client";

import { motion } from "framer-motion";
import type { ComponentPropsWithoutRef } from "react";

import { ease } from "@/lib/motion-tokens";
import { cn } from "@/utils/cn";

type CardProps = ComponentPropsWithoutRef<typeof motion.div> & {
  hover?: boolean;
};

export default function Card({ className, hover = false, children, ...props }: CardProps) {
  return (
    <motion.div
      whileHover={hover ? { y: -4, scale: 1.01 } : undefined}
      transition={{ duration: 0.2, ease: ease.out }}
      className={cn(
        "rounded-[32px] border border-[#E5E7EB] bg-white shadow-[0_18px_50px_rgba(148,163,184,0.12)]",
        className,
      )}
      {...props}
    >
      {children}
    </motion.div>
  );
}
