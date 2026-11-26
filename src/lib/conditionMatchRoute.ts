const matchRoute = /^#conditions\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i;
const matchId = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function conditionMatchIdFromHash(hash: string): string | null {
  return matchRoute.exec(hash)?.[1].toLowerCase() ?? null;
}

export function conditionMatchHash(id: string): string {
  return matchId.test(id) ? `#conditions/${id.toLowerCase()}` : "#conditions";
}
