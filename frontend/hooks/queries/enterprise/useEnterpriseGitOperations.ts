import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { enterpriseGitApi } from "@/services/enterprise/git-operations"

export function useGitBranches(repoUrl: string) {
  return useQuery({
    queryKey: ["git", "branches", repoUrl],
    queryFn: async () => {
      const res = await enterpriseGitApi.listBranches(repoUrl)
      return res.branches
    },
    enabled: !!repoUrl,
    staleTime: 30_000,
  })
}

export function useGitPullRequests(repoUrl: string, state: string = "open") {
  return useQuery({
    queryKey: ["git", "pull-requests", repoUrl, state],
    queryFn: async () => {
      const res = await enterpriseGitApi.listPullRequests(repoUrl, state)
      return res.pull_requests
    },
    enabled: !!repoUrl,
    staleTime: 30_000,
  })
}

export function useGitHistory(limit?: number) {
  return useQuery({
    queryKey: ["git", "history", limit],
    queryFn: async () => {
      const res = await enterpriseGitApi.getHistory(limit)
      return res.history
    },
    staleTime: 10_000,
  })
}

export function usePRSummary() {
  return useQuery({
    queryKey: ["git", "pr-summary"],
    queryFn: async () => {
      return enterpriseGitApi.getPRSummary()
    },
    staleTime: 30_000,
  })
}

export function useGenerateContext() {
  return useMutation({
    mutationFn: async (params: {
      mission_id?: string
      patch_plan_id?: string
      patch_candidate_id?: string
      repo_url?: string
      workspace_id?: string
      files_changed?: string
    }) => {
      return enterpriseGitApi.generateContext(params)
    },
  })
}

export function useCreateBranch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: {
      repo_url: string
      branch_name: string
      source_branch?: string
      workspace_id?: string
    }) => {
      return enterpriseGitApi.createBranch(payload)
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["git", "branches", data.repo_url] })
      queryClient.invalidateQueries({ queryKey: ["git", "history"] })
    },
  })
}

export function useCreateCommit() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: {
      repo_url: string
      branch: string
      description: string
      files: { path: string; content: string; encoding?: string; mode?: string }[]
      commit_type?: string
      scope?: string
      breaking?: boolean
      author?: Record<string, string>
      patch_candidate_id?: string
      mission_id?: string
    }) => {
      return enterpriseGitApi.createCommit(payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["git", "history"] })
    },
  })
}

export function useCreatePullRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: {
      repo_url: string
      title: string
      head: string
      base?: string
      body?: string
      reviewers?: string[]
      labels?: string[]
      milestone?: number
      mission_id?: string
      patch_plan_id?: string
      patch_candidate_id?: string
      workspace_id?: string
      files_changed?: string[]
      auto_context?: boolean
    }) => {
      return enterpriseGitApi.createPullRequest(payload)
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["git", "pull-requests", data.repo_url] })
      queryClient.invalidateQueries({ queryKey: ["git", "history"] })
      queryClient.invalidateQueries({ queryKey: ["git", "pr-summary"] })
    },
  })
}

export function useMergePullRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: {
      prNumber: number
      repo_url: string
      merge_method?: string
      commit_title?: string
      commit_message?: string
      require_approval?: boolean
    }) => {
      const { prNumber, ...rest } = payload
      return enterpriseGitApi.mergePullRequest(prNumber, rest)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["git"] })
    },
  })
}

export function useSyncIssue() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: {
      repo_url?: string
      pr_number?: number
      issue_number?: number
      issue_key?: string
      work_item_id?: number
      provider?: string
      action?: string
      comment?: string
      labels?: string[]
      status?: string
      state?: string
    }) => {
      return enterpriseGitApi.syncIssue(payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["git", "history"] })
    },
  })
}
