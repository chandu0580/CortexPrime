export function generateId(prefix?: string): string {
  const id = crypto.randomUUID?.() ?? Math.random().toString(36).substring(2, 15);
  return prefix ? `${prefix}-${id}` : id;
}

export function generateShortId(length: number = 12): string {
  return crypto.randomUUID?.().replace(/-/g, '').substring(0, length)
    ?? Math.random().toString(36).substring(2, length + 2);
}
