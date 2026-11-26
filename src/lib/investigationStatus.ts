export function investigationStatusLabel(state: string, approvalCurrent?: boolean): string {
  if (state === "approved") return approvalCurrent ? "Approved · current" : "Approval needs review";
  return ({ awaiting_review: "Awaiting review", rejected: "Returned for revision", dispatched: "Work order planned", unavailable: "Link unavailable" } as Record<string, string>)[state] ?? "Status unavailable";
}
