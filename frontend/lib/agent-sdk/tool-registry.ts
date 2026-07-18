import type { ToolSpec } from './types';

const toolRegistry = new Map<string, ToolSpec>();

export function registerTool(spec: ToolSpec): void {
  toolRegistry.set(spec.name, spec);
}

export function getRegisteredTools(): ToolSpec[] {
  return Array.from(toolRegistry.values());
}

export function clearRegistry(): void {
  toolRegistry.clear();
}
