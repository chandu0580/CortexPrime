import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { executionApi } from '@/services/enterprise/execution';
import { queryKeys } from '@/lib/query';

export function useExecutionDashboard() {
  return useQuery({
    queryKey: queryKeys.execution.dashboard(),
    queryFn: () => executionApi.dashboard(),
  });
}

export function useExecutions(status?: string, repository?: string) {
  return useQuery({
    queryKey: [...queryKeys.execution.list(), { status, repository }],
    queryFn: () => executionApi.list({ status, repository }),
  });
}

export function useExecution(executionId: string) {
  return useQuery({
    queryKey: queryKeys.execution.detail(executionId),
    queryFn: () => executionApi.get(executionId),
    enabled: !!executionId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && (data.status === 'running' || data.status === 'pending')) return 3000;
      return false;
    },
  });
}

export function useCreateExecution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: executionApi.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.execution.all });
      qc.invalidateQueries({ queryKey: queryKeys.execution.dashboard() });
    },
  });
}

export function useStartExecution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ executionId, autoApprove }: { executionId: string; autoApprove?: boolean }) =>
      executionApi.start(executionId, autoApprove),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: queryKeys.execution.detail(data.execution_id) });
      qc.invalidateQueries({ queryKey: queryKeys.execution.dashboard() });
    },
  });
}

export function useStartAsyncExecution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ executionId, autoApprove }: { executionId: string; autoApprove?: boolean }) =>
      executionApi.startAsync(executionId, autoApprove),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.execution.all });
      qc.invalidateQueries({ queryKey: queryKeys.execution.dashboard() });
    },
  });
}

export function useCancelExecution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (executionId: string) => executionApi.cancel(executionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.execution.all });
      qc.invalidateQueries({ queryKey: queryKeys.execution.dashboard() });
    },
  });
}

export function useRollbackExecution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (executionId: string) => executionApi.rollback(executionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.execution.all });
      qc.invalidateQueries({ queryKey: queryKeys.execution.dashboard() });
    },
  });
}

export function useRetryExecution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (executionId: string) => executionApi.retry(executionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.execution.all });
      qc.invalidateQueries({ queryKey: queryKeys.execution.dashboard() });
    },
  });
}
