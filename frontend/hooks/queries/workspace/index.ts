"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchWorkspaceExecutive, fetchWorkspaceMission, fetchWorkspacePortfolio, fetchWorkspaceIntelligence } from "@/services/workspace"

export function useWorkspaceExecutive() {
  return useQuery({
    queryKey: ["workspace", "executive"],
    queryFn: fetchWorkspaceExecutive,
  })
}

export function useWorkspaceMission() {
  return useQuery({
    queryKey: ["workspace", "mission"],
    queryFn: fetchWorkspaceMission,
  })
}

export function useWorkspacePortfolio() {
  return useQuery({
    queryKey: ["workspace", "portfolio"],
    queryFn: fetchWorkspacePortfolio,
  })
}

export function useWorkspaceIntelligence() {
  return useQuery({
    queryKey: ["workspace", "intelligence"],
    queryFn: fetchWorkspaceIntelligence,
  })
}
