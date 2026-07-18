import { api } from '@/services/api';
import type {
  EngineeringTask,
  EngineeringPlan,
  EngineeringReport,
  ExecutionStatus,
  ExecutiveDashboardStats,
  SupportedTaskType,
} from '@/types/engineering-executive';

const BASE = '/api/engineering-executive';

export const engineeringExecutiveApi = {
  // Tasks
  createTask: (description: string, repoUrl?: string, branch?: string) =>
    api.post<EngineeringTask>(`${BASE}/tasks`, { description, repo_url: repoUrl, branch }),

  listTasks: (status?: string) => {
    const params = status ? `?status=${encodeURIComponent(status)}` : '';
    return api.get<EngineeringTask[]>(`${BASE}/tasks${params}`);
  },

  getTask: (taskId: string) =>
    api.get<EngineeringTask>(`${BASE}/tasks/${taskId}`),

  deleteTask: (taskId: string) =>
    api.delete<{ status: string }>(`${BASE}/tasks/${taskId}`),

  // Plans
  createPlan: (taskId: string) =>
    api.post<EngineeringPlan>(`${BASE}/plans`, { task_id: taskId }),

  listPlans: (status?: string) => {
    const params = status ? `?status=${encodeURIComponent(status)}` : '';
    return api.get<EngineeringPlan[]>(`${BASE}/plans${params}`);
  },

  getPlan: (planId: string) =>
    api.get<EngineeringPlan>(`${BASE}/plans/${planId}`),

  deletePlan: (planId: string) =>
    api.delete<{ status: string }>(`${BASE}/plans/${planId}`),

  // Execution
  executePlan: (planId: string) =>
    api.post<EngineeringPlan>(`${BASE}/plans/${planId}/execute`),

  getExecutionStatus: (planId: string) =>
    api.get<ExecutionStatus>(`${BASE}/plans/${planId}/status`),

  // Reports
  generateReport: (planId: string) =>
    api.post<EngineeringReport>(`${BASE}/plans/${planId}/report`),

  getReport: (reportId: string) =>
    api.get<EngineeringReport>(`${BASE}/reports/${reportId}`),

  listReports: () =>
    api.get<EngineeringReport[]>(`${BASE}/reports`),

  // Dashboard
  getDashboard: () =>
    api.get<ExecutiveDashboardStats>(`${BASE}/dashboard`),

  getSupportedTypes: () =>
    api.get<SupportedTaskType[]>(`${BASE}/supported-types`),
};
