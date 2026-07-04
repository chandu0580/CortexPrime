"use client"
import { motion, AnimatePresence } from "framer-motion"
import { streamingText } from "@/lib/animations"
import { cn } from "@/utils/cn"

// ==========================================
// STREAM ANIMATION
// ==========================================

interface StreamAnimationProps {
    text: string
    isStreaming?: boolean
    className?: string
}

export default function StreamAnimation({ text, isStreaming, className }: StreamAnimationProps) {
    const words = text.split(" ")

    return (
        <span className={cn("inline", className)}>
            <AnimatePresence mode="wait">
                {words.map((word, i) => (
                    <motion.span
                        key={`${i}-${word}`}
                        variants={streamingText}
                        initial="hidden"
                        animate="visible"
                        className="inline-block mr-1"
                    >
                        {word}
                    </motion.span>
                ))}
            </AnimatePresence>
            {isStreaming && (
                <span className="inline-block w-0.5 h-4 bg-[#82c0a4] ml-0.5 animate-stream-cursor" />
            )}
        </span>
    )
}
