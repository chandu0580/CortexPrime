/**
 * CortexPrime — Mouse-Reactive Background V4
 * Parallax radial gradient that follows cursor.
 * Drop-in replacement for static landing background.
 */
"use client"

import { useEffect, useRef } from "react"
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion"

export default function MouseReactiveBg() {
    const mouseX = useMotionValue(0.5)   // 0-1
    const mouseY = useMotionValue(0.5)

    const springX = useSpring(mouseX, { stiffness: 60, damping: 20 })
    const springY = useSpring(mouseY, { stiffness: 60, damping: 20 })

    // Map 0-1 to gradient position
    const gradX = useTransform(springX, [0, 1], ["20%", "80%"])
    const gradY = useTransform(springY, [0, 1], ["20%", "80%"])

    useEffect(() => {
        function onMove(e: MouseEvent) {
            mouseX.set(e.clientX / window.innerWidth)
            mouseY.set(e.clientY / window.innerHeight)
        }
        window.addEventListener("mousemove", onMove)
        return () => window.removeEventListener("mousemove", onMove)
    }, [mouseX, mouseY])

    return (
        <div style={{ position: "fixed", inset: 0, zIndex: 0, pointerEvents: "none", overflow: "hidden" }} aria-hidden>
            {/* Primary reactive blob */}
            <motion.div
                style={{
                    position:     "absolute",
                    width:        800,
                    height:       800,
                    borderRadius: "50%",
                    background:   "radial-gradient(circle, rgba(130,192,164,0.07) 0%, transparent 70%)",
                    left:         gradX,
                    top:          gradY,
                    transform:    "translate(-50%, -50%)",
                    filter:       "blur(80px)",
                }}
            />
            {/* Static ambient blobs */}
            <motion.div
                animate={{ scale: [1, 1.1, 1], opacity: [0.3, 0.5, 0.3] }}
                transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
                style={{
                    position:     "absolute",
                    top:          "-10%",
                    right:        "-5%",
                    width:        600,
                    height:       600,
                    borderRadius: "50%",
                    background:   "radial-gradient(circle, rgba(74,140,112,0.06) 0%, transparent 65%)",
                    filter:       "blur(60px)",
                }}
            />
            <motion.div
                animate={{ scale: [1.1, 1, 1.1], opacity: [0.2, 0.4, 0.2] }}
                transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 2 }}
                style={{
                    position:     "absolute",
                    bottom:       "5%",
                    left:         "10%",
                    width:        500,
                    height:       500,
                    borderRadius: "50%",
                    background:   "radial-gradient(circle, rgba(124,58,237,0.05) 0%, transparent 65%)",
                    filter:       "blur(60px)",
                }}
            />
            {/* Grid overlay */}
            <div style={{
                position:   "absolute",
                inset:      0,
                backgroundImage: `
                    linear-gradient(rgba(130,192,164,0.03) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(130,192,164,0.03) 1px, transparent 1px)
                `,
                backgroundSize: "60px 60px",
            }} />
        </div>
    )
}
