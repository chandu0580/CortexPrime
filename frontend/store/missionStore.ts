import { create } from "zustand"

// ==========================================
// MISSION STAGE TYPES
// ==========================================

export type MissionStage =
    | "idle"
    | "initialized"
    | "planning"
    | "researching"
    | "executing"
    | "validating"
    | "reflecting"
    | "completed"

export const MISSION_STAGES: MissionStage[] = [
    "initialized",
    "planning",
    "researching",
    "executing",
    "validating",
    "reflecting",
    "completed",
]

export const STAGE_LABELS: Record<MissionStage, string> = {
    idle:        "Idle",
    initialized: "Init",
    planning:    "Planning",
    researching: "Research",
    executing:   "Executing",
    validating:  "Validating",
    reflecting:  "Reflecting",
    completed:   "Complete",
}

export const STAGE_AGENTS: Record<MissionStage, string> = {
    idle:        "",
    initialized: "orchestrator",
    planning:    "planner",
    researching: "research",
    executing:   "orchestrator",
    validating:  "critic",
    reflecting:  "memory",
    completed:   "",
}

// ==========================================
// MISSION STORE
// ==========================================

interface MissionStore {
    goal:        string | null
    stage:       MissionStage
    stageIndex:  number        // index into MISSION_STAGES (-1 = idle)
    startedAt:   string | null
    completedAt: string | null
    progress:    number        // 0-100

    startMission:    (goal: string) => void
    advanceStage:    () => void
    advanceStageTo:  (target: MissionStage) => void
    completeMission: () => void
    resetMission:    () => void
    setProgress:     (p: number) => void
}

export const useMissionStore = create<MissionStore>((set) => ({
    goal:        null,
    stage:       "idle",
    stageIndex:  -1,
    startedAt:   null,
    completedAt: null,
    progress:    0,

    startMission: (goal) => set({
        goal,
        stage:       "initialized",
        stageIndex:  0,
        startedAt:   new Date().toISOString(),
        completedAt: null,
        progress:    2,
    }),

    advanceStage: () => set((s) => {
        if (s.stage === "idle" || s.stage === "completed") return {}
        const nextIndex = s.stageIndex + 1
        if (nextIndex >= MISSION_STAGES.length) {
            return {
                stage:       "completed" as const,
                stageIndex:  MISSION_STAGES.length - 1,
                progress:    100,
                completedAt: new Date().toISOString(),
            }
        }
        const nextStage = MISSION_STAGES[nextIndex]
        const progress  = Math.round((nextIndex / (MISSION_STAGES.length - 1)) * 95 + 2)
        return { stage: nextStage, stageIndex: nextIndex, progress }
    }),

    advanceStageTo: (target) => set((s) => {
        if (s.stage === "completed") return {}
        const targetIndex = MISSION_STAGES.indexOf(target)
        if (targetIndex < 0) return {}
        // Only advance forward, never backward
        if (targetIndex <= s.stageIndex) return {}
        const progress = Math.round((targetIndex / (MISSION_STAGES.length - 1)) * 95 + 2)
        return { stage: target, stageIndex: targetIndex, progress }
    }),

    completeMission: () => set({
        stage:       "completed",
        stageIndex:  MISSION_STAGES.length - 1,
        progress:    100,
        completedAt: new Date().toISOString(),
    }),

    resetMission: () => set({
        goal:        null,
        stage:       "idle",
        stageIndex:  -1,
        startedAt:   null,
        completedAt: null,
        progress:    0,
    }),

    setProgress: (p) => set({ progress: p }),
}))
