import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { engineeringExecutiveApi } from '@/services/enterprise/engineering-executive';

const KEYS = {
  tasks: ['engineering-executive', 'tasks'] as const,
  task: (id: string) => ['engineering-executive', 'tasks', id] as const,
  plans: ['engineering-executive', 'plans'] as const,
  plan: (id: string) => ['engineering-executive', 'plans', id] as const,
  status: (id: string) => ['engineering-executive', 'status', id] as const,
  reports: ['engineering-executive', 'reports'] as const,
  report: (id: string) => ['engineering-executive', 'reports', id] as const,
  dashboard: ['engineering-executive', 'dashboard'] as const,
  supported: ['engineering-executive', 'supported-types'] as const,
};

export function useEngineeringExecutiveDashboard() {
  return useQuery({
    queryKey: KEYS.dashboard,
    queryFn: () => engineeringExecutiveApi.getDashboard(),
  });
}

export function useSupportedTaskTypes() {
  return useQuery({
    queryKey: KEYS.supported,
    queryFn: () => engineeringExecutiveApi.getSupportedTypes(),
  });
}

export function useEngineeringTasks(status?: string) {
  return useQuery({
    queryKey: [...KEYS.tasks, status],
    queryFn: () => engineeringExecutiveApi.listTasks(status),
  });
}

export function useEngineeringTask(taskId: string) {
  return useQuery({
    queryKey: KEYS.task(taskId),
    queryFn: () => engineeringExecutiveApi.getTask(taskId),
    enabled: !!taskId,
  });
}

export function useCreateEngineeringTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ description, repoUrl, branch }: { description: string; repoUrl?: string; branch?: string }) =>
      engineeringExecutiveApi.createTask(description, repoUrl, branch),
    onSuccess: () => { qc.invalidateQueries({ queryKey: KEYS.tasks }); qc.invalidateQueries({ queryKey: KEYS.dashboard }); },
  });
}

export function useDeleteEngineeringTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => engineeringExecutiveApi.deleteTask(taskId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: KEYS.tasks }); qc.invalidateQueries({ queryKey: KEYS.dashboard }); },
  });
}

export function useEngineeringPlans(status?: string) {
  return useQuery({
    queryKey: [...KEYS.plans, status],
    queryFn: () => engineeringExecutiveApi.listPlans(status),
  });
}

export function useEngineeringPlan(planId: string) {
  return useQuery({
    queryKey: KEYS.plan(planId),
    queryFn: () => engineeringExecutiveApi.getPlan(planId),
    enabled: !!planId,
  });
}

export function useCreateEngineeringPlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => engineeringExecutiveApi.createPlan(taskId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: KEYS.plans }); qc.invalidateQueries({ queryKey: KEYS.dashboard }); },
  });
}

export function useExecuteEngineeringPlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (planId: string) => engineeringExecutiveApi.executePlan(planId),
    onSuccess: (_, planId) => { qc.invalidateQueries({ queryKey: KEYS.plan(planId) }); qc.invalidateQueries({ queryKey: KEYS.status(planId) }); qc.invalidateQueries({ queryKey: KEYS.dashboard }); },
  });
}

export function useEngineeringExecutionStatus(planId: string) {
  return useQuery({
    queryKey: KEYS.status(planId),
    queryFn: () => engineeringExecutiveApi.getExecutionStatus(planId),
    enabled: !!planId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && (data.status === 'running' || data.status === 'pending')) return 2000;
      return false;
    },
  });
}

export function useEngineeringReports() {
  return useQuery({
    queryKey: KEYS.reports,
    queryFn: () => engineeringExecutiveApi.listReports(),
  });
}

export function useEngineeringReport(reportId: string) {
  return useQuery({
    queryKey: KEYS.report(reportId),
    queryFn: () => engineeringExecutiveApi.getReport(reportId),
    enabled: !!reportId,
  });
}

export function useGenerateEngineeringReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (planId: string) => engineeringExecutiveApi.generateReport(planId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: KEYS.reports }); qc.invalidateQueries({ queryKey: KEYS.dashboard }); },
  });
}
