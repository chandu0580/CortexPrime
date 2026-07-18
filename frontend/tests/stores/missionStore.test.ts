import { describe, it, expect, beforeEach } from "vitest"
import { useMissionStore } from "@/store/missionStore"
import type { MissionStage } from "@/store/missionStore"

const INITIAL_STATE = {
  goal: null,
  stage: "idle" as MissionStage,
  stageIndex: -1,
  startedAt: null,
  completedAt: null,
  progress: 0,
}

describe("useMissionStore", () => {
  beforeEach(() => {
    useMissionStore.setState(INITIAL_STATE)
  })

  it("has correct initial state", () => {
    const state = useMissionStore.getState()
    expect(state.goal).toBeNull()
    expect(state.stage).toBe("idle")
    expect(state.stageIndex).toBe(-1)
    expect(state.progress).toBe(0)
    expect(state.startedAt).toBeNull()
    expect(state.completedAt).toBeNull()
  })

  it("startMission sets goal stage initialized stageIndex 0 and progress 2", () => {
    useMissionStore.getState().startMission("test goal")
    const state = useMissionStore.getState()
    expect(state.goal).toBe("test goal")
    expect(state.stage).toBe("initialized")
    expect(state.stageIndex).toBe(0)
    expect(state.progress).toBe(2)
    expect(state.startedAt).not.toBeNull()
    expect(state.completedAt).toBeNull()
  })

  it("advanceStage iterates through all stages in order", () => {
    useMissionStore.getState().startMission("test")

    const expected: [MissionStage, number, number][] = [
      ["planning", 1, 18],
      ["researching", 2, 34],
      ["executing", 3, 50],
      ["validating", 4, 65],
      ["reflecting", 5, 81],
      ["completed", 6, 97],
    ]

    for (const [nextStage, nextIndex, nextProgress] of expected) {
      useMissionStore.getState().advanceStage()
      const state = useMissionStore.getState()
      expect(state.stage).toBe(nextStage)
      expect(state.stageIndex).toBe(nextIndex)
      expect(state.progress).toBe(nextProgress)
    }
  })

  it("advanceStage does nothing when stage is idle", () => {
    useMissionStore.getState().advanceStage()
    const state = useMissionStore.getState()
    expect(state.stage).toBe("idle")
    expect(state.stageIndex).toBe(-1)
  })

  it("advanceStage does nothing when stage is completed", () => {
    useMissionStore.getState().startMission("test")

    for (let i = 0; i < 7; i++) {
      useMissionStore.getState().advanceStage()
    }

    let state = useMissionStore.getState()
    expect(state.stage).toBe("completed")
    expect(state.stageIndex).toBe(6)
    expect(state.progress).toBe(97)

    useMissionStore.getState().advanceStage()

    state = useMissionStore.getState()
    expect(state.stage).toBe("completed")
  })

  it("advanceStageTo only moves forward ignores backward or same stage", () => {
    useMissionStore.getState().startMission("test")
    useMissionStore.getState().advanceStageTo("executing")

    expect(useMissionStore.getState().stage).toBe("executing")

    useMissionStore.getState().advanceStageTo("researching")

    expect(useMissionStore.getState().stage).toBe("executing")

    useMissionStore.getState().advanceStageTo("executing")

    expect(useMissionStore.getState().stage).toBe("executing")

    useMissionStore.getState().advanceStageTo("completed")

    expect(useMissionStore.getState().stage).toBe("completed")
  })

  it("advanceStageTo does nothing when stage is completed", () => {
    useMissionStore.getState().startMission("test")
    useMissionStore.getState().advanceStageTo("completed")

    useMissionStore.getState().advanceStageTo("planning")

    expect(useMissionStore.getState().stage).toBe("completed")
  })

  it("completeMission sets stage completed and progress 100", () => {
    useMissionStore.getState().startMission("test")
    useMissionStore.getState().completeMission()

    const state = useMissionStore.getState()
    expect(state.stage).toBe("completed")
    expect(state.stageIndex).toBe(6)
    expect(state.progress).toBe(100)
    expect(state.completedAt).not.toBeNull()
  })

  it("resetMission resets to initial state", () => {
    useMissionStore.getState().startMission("test")
    useMissionStore.getState().advanceStageTo("executing")
    useMissionStore.getState().resetMission()

    const state = useMissionStore.getState()
    expect(state.goal).toBeNull()
    expect(state.stage).toBe("idle")
    expect(state.stageIndex).toBe(-1)
    expect(state.startedAt).toBeNull()
    expect(state.completedAt).toBeNull()
    expect(state.progress).toBe(0)
  })

  it("setProgress updates progress value", () => {
    useMissionStore.getState().setProgress(42)
    expect(useMissionStore.getState().progress).toBe(42)
  })
})
