"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { getMissions, getMissionReplay, getMissionReplayTimeline } from "@/services/mission-control/missions"
import { planMission, getPlan } from "@/services/mission-control/planner"
import { getActiveMissions, getEvents, getRuntimeTelemetry } from "@/services/mission-control/execution"
import type { PlanInput } from "@/services/mission-control/planner"

export function useMissions() {
    return useQuery({
        queryKey: queryKeys.missionControl.missions(),
        queryFn: getMissions,
    })
}

export function useActiveMissions() {
    return useQuery({
        queryKey: [...queryKeys.missionControl.missions(), "active"],
        queryFn: getActiveMissions,
    })
}

export function useMissionEvents() {
    return useQuery({
        queryKey: [...queryKeys.missionControl.missions(), "events"],
        queryFn: getEvents,
    })
}

export function useRuntimeTelemetry() {
    return useQuery({
        queryKey: [...queryKeys.missionControl.missions(), "telemetry"],
        queryFn: getRuntimeTelemetry,
    })
}

export function useMissionReplay(executionId: string | null) {
    return useQuery({
        queryKey: [...queryKeys.missionControl.all, "replay", executionId],
        queryFn: () => getMissionReplay(executionId!),
        enabled: !!executionId,
    })
}

export function useMissionReplayTimeline(executionId: string | null) {
    return useQuery({
        queryKey: [...queryKeys.missionControl.all, "replay", executionId, "timeline"],
        queryFn: () => getMissionReplayTimeline(executionId!),
        enabled: !!executionId,
    })
}

export function usePlanMission() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: (input: PlanInput) => planMission(input),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: queryKeys.missionControl.missions() })
        },
    })
}

export function useMissionPlan(executionId: string | null) {
    return useQuery({
        queryKey: [...queryKeys.missionControl.all, "plan", executionId],
        queryFn: () => getPlan(executionId!),
        enabled: !!executionId,
    })
}
