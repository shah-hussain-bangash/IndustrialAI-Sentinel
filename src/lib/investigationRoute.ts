export function investigationIdFromHash(hash: string): string | null {
  return /^#intelligence\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i.exec(hash)?.[1] ?? null;
}
