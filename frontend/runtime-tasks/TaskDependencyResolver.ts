import type { ExecutionTask, TaskDependency, DependencyType } from "./types"
import { generateId } from "./shared"

const dependencies = new Map<string, TaskDependency>()

export const TaskDependencyResolver = {
  async addDependency(
    taskId: string,
    dependsOnTaskId: string,
    type: DependencyType = "hard",
  ): Promise<TaskDependency> {
    const dep: TaskDependency = {
      id: generateId("dep"),
      taskId,
      dependsOnTaskId,
      type,
      satisfied: false,
      details: `${taskId} → ${dependsOnTaskId} (${type})`,
    }
    dependencies.set(dep.id, dep)
    return dep
  },

  async getDependencies(taskId: string): Promise<TaskDependency[]> {
    return Array.from(dependencies.values()).filter((d) => d.taskId === taskId)
  },

  async getDependents(taskId: string): Promise<TaskDependency[]> {
    return Array.from(dependencies.values()).filter((d) => d.dependsOnTaskId === taskId)
  },

  async evaluateDependencies(taskId: string, allTasks: ExecutionTask[]): Promise<TaskDependency[]> {
    const deps = await TaskDependencyResolver.getDependencies(taskId)
    const evaluated: TaskDependency[] = []

    for (const dep of deps) {
      const dependencyTask = allTasks.find((t) => t.id === dep.dependsOnTaskId)
      let satisfied = false

      if (dependencyTask) {
        if (dep.type === "hard") {
          satisfied = dependencyTask.state === "COMPLETED"
        } else if (dep.type === "soft") {
          satisfied = dependencyTask.state === "COMPLETED" || dependencyTask.state === "FAILED"
        } else if (dep.type === "signal") {
          satisfied = dependencyTask.state === "COMPLETED" || dependencyTask.state === "RUNNING"
        }
      }

      const evaluatedDep: TaskDependency = { ...dep, satisfied }
      dependencies.set(dep.id, evaluatedDep)
      evaluated.push(evaluatedDep)
    }

    return evaluated
  },

  async areDependenciesSatisfied(taskId: string, allTasks: ExecutionTask[]): Promise<boolean> {
    const deps = await TaskDependencyResolver.evaluateDependencies(taskId, allTasks)
    const hardDeps = deps.filter((d) => d.type === "hard")
    return hardDeps.every((d) => d.satisfied)
  },

  async getUnsatisfiedHardDeps(taskId: string, allTasks: ExecutionTask[]): Promise<TaskDependency[]> {
    const deps = await TaskDependencyResolver.evaluateDependencies(taskId, allTasks)
    return deps.filter((d) => d.type === "hard" && !d.satisfied)
  },

  async removeDependency(depId: string): Promise<void> {
    dependencies.delete(depId)
  },

  async clearTaskDependencies(taskId: string): Promise<void> {
    const deps = await TaskDependencyResolver.getDependencies(taskId)
    for (const dep of deps) {
      dependencies.delete(dep.id)
    }
  },
}
