// ==========================================
// FRAMER MOTION ANIMATION VARIANTS
// Re-exports all variants from motion-tokens so
// existing code continues to work, but durations
// are now sourced from the canonical token set.
// ==========================================

export { variants as motionVariants, dur, ease, spring, stagger, loop, transition } from "@/lib/motion-tokens"

// ── Legacy named exports (kept for backwards compat) ─────────────────────

export const fadeIn = {
    hidden:  { opacity: 0 },
    visible: { opacity: 1, transition: { duration: 0.30 } },
}

export const fadeInUp = {
    hidden:  { opacity: 0, y: 16 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.30, ease: "easeOut" as const } },
}

export const slideInLeft = {
    hidden:  { opacity: 0, x: -20 },
    visible: { opacity: 1, x: 0, transition: { duration: 0.30, ease: "easeOut" as const } },
}

export const slideInRight = {
    hidden:  { opacity: 0, x: 20 },
    visible: { opacity: 1, x: 0, transition: { duration: 0.30, ease: "easeOut" as const } },
}

export const scaleIn = {
    hidden:  { opacity: 0, scale: 0.92 },
    visible: { opacity: 1, scale: 1, transition: { duration: 0.20, ease: "easeOut" as const } },
}

export const staggerContainer = {
    hidden:  {},
    visible: { transition: { staggerChildren: 0.07 } },
}

export const glowPulse = {
    initial: { opacity: 0.6, scale: 1 },
    animate: {
        opacity:    [0.6, 1, 0.6],
        scale:      [1, 1.04, 1],
        transition: { duration: 2, repeat: Infinity, ease: "easeInOut" },
    },
}

export const neuralPulse = {
    initial: { opacity: 0.4 },
    animate: {
        opacity:    [0.4, 0.9, 0.4],
        transition: { duration: 1.5, repeat: Infinity, ease: "easeInOut" },
    },
}

export const streamingText = {
    hidden:  { opacity: 0, y: 4 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.15 } },
}
