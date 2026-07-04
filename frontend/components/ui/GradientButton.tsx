"use client"
import { motion } from "framer-motion"
import { cn } from "@/utils/cn"

// ==========================================
// GRADIENT BUTTON
// ==========================================

interface GradientButtonProps {
    children: React.ReactNode
    onClick?: () => void
    disabled?: boolean
    size?: "sm" | "md" | "lg"
    className?: string
    type?: "button" | "submit"
    loading?: boolean
}

const sizeMap = {
    sm: "px-3 py-1.5 text-xs",
    md: "px-5 py-2.5 text-sm",
    lg: "px-7 py-3 text-base",
}

export default function GradientButton({
    children, onClick, disabled, size = "md", className, type = "button", loading,
}: GradientButtonProps) {
    return (
        <motion.button
            type={type}
            whileHover={{ scale: disabled ? 1 : 1.02 }}
            whileTap={{ scale: disabled ? 1 : 0.97 }}
            onClick={onClick}
            disabled={disabled || loading}
            className={cn(
                "relative inline-flex items-center justify-center gap-2 rounded-lg font-semibold",
                "bg-gradient-to-r from-[#82c0a4] to-[#4a8c70]",
                "text-white shadow-lg shadow-[#82c0a4]/20",
                "transition-opacity duration-150",
                "disabled:opacity-40 disabled:cursor-not-allowed",
                sizeMap[size],
                className
            )}
        >
            {loading && (
                <span className="h-3.5 w-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
            )}
            {children}
        </motion.button>
    )
}
