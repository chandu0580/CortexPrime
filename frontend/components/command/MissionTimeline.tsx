"use client"
import { motion } from "framer-motion"
import { useMissionStore, MISSION_STAGES, STAGE_LABELS } from "@/store/missionStore"

// ==========================================
// MISSION TIMELINE
// ==========================================

export default function MissionTimeline() {
    const { stage, stageIndex, goal, progress } = useMissionStore()

    if (stage === "idle" || !goal) return null

    const isComplete = stage === "completed"

    return (
        <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.35 }}
            className="px-4 py-3 bg-white shrink-0"
            style={{ borderBottom: "1px solid #e8f5ee" }}
        >
            {/* Top row: label + goal */}
            <div className="flex items-center justify-between mb-2.5 gap-3">
                <div className="flex items-center gap-2">
                    {/* Live pulse */}
                    {!isComplete && (
                        <motion.div
                            className="w-1.5 h-1.5 rounded-full shrink-0"
                            style={{ background: "#82c0a4" }}
                            animate={{ scale: [1, 1.7, 1], opacity: [1, 0.4, 1] }}
                            transition={{ duration: 1.6, repeat: Infinity }}
                        />
                    )}
                    {isComplete && (
                        <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: "#4a8c70" }} />
                    )}
                    <span className="text-[8px] font-black tracking-widest uppercase"
                        style={{ color: isComplete ? "#4a8c70" : "#82c0a4" }}>
                        {isComplete ? "Mission Complete" : "Active Mission"}
                    </span>
                </div>
                <p className="text-[9px] text-[#737373] truncate max-w-[60%]" title={goal}>
                    {goal}
                </p>
            </div>

            {/* Stage track */}
            <div className="relative flex items-start">
                {/* Track background */}
                <div
                    className="absolute left-0 right-0 h-0.5 rounded-full"
                    style={{ top: "7px", background: "#dceee4" }}
                />
                {/* Progress fill */}
                <motion.div
                    className="absolute left-0 h-0.5 rounded-full"
                    style={{
                        top:        "7px",
                        background: "linear-gradient(90deg, #82c0a4, #4a8c70)",
                    }}
                    initial={false}
                    animate={{ width: isComplete ? "100%" : `${progress}%` }}
                    transition={{ duration: 1.2, ease: "easeInOut" }}
                />

                {/* Stage dots */}
                {MISSION_STAGES.map((s, i) => {
                    const isDone    = isComplete || i < stageIndex
                    const isActive  = !isComplete && i === stageIndex
                    const isPending = !isComplete && i > stageIndex

                    return (
                        <div key={s} className="relative flex-1 flex flex-col items-center">
                            {/* Dot */}
                            <motion.div
                                className="relative z-10 w-3.5 h-3.5 rounded-full flex items-center justify-center"
                                style={{
                                    background: isDone
                                        ? "#4a8c70"
                                        : isActive
                                            ? "#82c0a4"
                                            : "#dceee4",
                                    border: `2px solid ${isDone ? "#4a8c70" : isActive ? "#82c0a4" : "#d1d5db"}`,
                                }}
                                animate={isActive ? {
                                    boxShadow: [
                                        "0 0 0 0 rgba(130,192,164,0.4)",
                                        "0 0 0 5px rgba(130,192,164,0)",
                                    ],
                                } : {}}
                                transition={isActive ? {
                                    duration: 1.4, repeat: Infinity, ease: "easeOut",
                                } : {}}
                            >
                                {isDone && (
                                    <svg width="6" height="6" viewBox="0 0 6 6" fill="none">
                                        <path d="M1 3L2.5 4.5L5 1.5" stroke="white" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                                    </svg>
                                )}
                                {isActive && (
                                    <motion.div
                                        className="w-1.5 h-1.5 rounded-full bg-white"
                                        animate={{ scale: [1, 1.4, 1] }}
                                        transition={{ duration: 0.9, repeat: Infinity }}
                                    />
                                )}
                            </motion.div>

                            {/* Label */}
                            <span
                                className="mt-1.5 text-[7px] font-semibold text-center leading-tight px-0.5"
                                style={{
                                    color: isDone
                                        ? "#4a8c70"
                                        : isActive
                                            ? "#82c0a4"
                                            : "#a3a3a3",
                                    fontWeight: isActive ? 800 : 600,
                                }}
                            >
                                {STAGE_LABELS[s]}
                            </span>
                        </div>
                    )
                })}
            </div>
        </motion.div>
    )
}
