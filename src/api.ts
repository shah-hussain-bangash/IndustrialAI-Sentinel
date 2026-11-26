export interface User {
  mfa_setup_required?: boolean;
  site_ids?: string[];
  id: string;
  name: string;
  email: string;
  role: string;
  sites: string[];
}
export type LoginResponse = {user:User;csrf:string;mfa_required?:false} | {mfa_required:true;challenge_csrf:string;message:string};
export interface Reading {
  fingerprint?: string;
  timestamp: number;
  vibration: number;
  temperature: number;
  pressure: number;
  flow: number;
  quality: string;
}
export interface Asset {
  site_id?: string;
  id: string;
  tag: string;
  name: string;
  kind: string;
  site: string;
  location: string;
  criticality: string;
  manufacturer: string;
  installed: string;
  version: number;
  threshold: number;
  health: number | null;
  status: string;
  anomaly: boolean;
  anomaly_score: number | null;
  reading: Reading | null;
  freshness_seconds: number | null;
  sensor_count: number;
  source: string;
  vibration_trend: number[];
}
export interface Episode {
  id: string;
  asset_id: string;
  asset_tag: string;
  asset_name: string;
  site: string;
  title: string;
  severity: string;
  state: string;
  created: number;
  version: number;
}
export interface Evidence {
  id: string;
  document_id: string;
  title: string;
  page: number;
  version: string;
  text: string;
  score: number;
  kind: string;
}
export interface ConditionOrigin {
  match_id: string;
  asset: { tag: string; name: string; site: string };
  rule: { id: string; version: number; name: string; settings: { channel: string; threshold: number; hysteresis: number; persistence_seconds: number; maximum_gap_seconds: number }; actor_name: string; created: number; reason: string };
  match: { signal_state: string; started_at: number; triggered_at: number; ended_at: number | null };
  snapshot: { id: string; timestamp: number; quality: string; signals: { channel: string; value: number | null; unit: string }[] };
  analysis_snapshot: { id: string; timestamp: number; quality: string; signals: { channel: string; value: number | null; unit: string }[] };
  prepared_at: number;
  investigation_note: string;
  boundary: string;
}
export interface Investigation {
  id: string;
  asset_id: string;
  asset_tag: string;
  asset_name: string;
  site: string;
  title: string;
  state: string;
  created: number;
  version: number;
  payload: {
    observations: string[];
    possible_causes: string[];
    recommendation: string;
    checklist: string[];
    evidence: Evidence[];
    data_gaps: string[];
    engine: string;
    model_version: string;
    requires_approval: boolean;
    priority: string;
    condition_origin?: ConditionOrigin;
  };
  creator: string;
  creator_id: string;
  approver: string | null;
  approved_until: number | null;
  decision_reason: string;
}
export interface WorkOrder {
  id: string;
  reference: string;
  asset_id: string;
  investigation_id: string;
  title: string;
  priority: string;
  status: string;
  assignee: string;
  due_date: string;
  external_ref: string | null;
  created: number;
  version: number;
  outcome: string;
  asset_tag: string;
  asset_name: string;
  site: string;
  integration: string;
}
export interface DocumentInfo {
  original_available?: boolean;
  original_bytes?: number | null;
  original_status?: string;
  site_id?: string;
  id: string;
  title: string;
  filename: string;
  site: string;
  kind: string;
  version: string;
  page_count: number;
  created: number;
  checksum: string;
}
export interface AuditEvent {
  site_id?: string;
  id: string;
  actor: string;
  action: string;
  target: string;
  details: string;
  created: number;
  site: string;
}
export interface ModelMetrics {
  version: string;
  algorithm: string;
  training_samples: number;
  evaluation_samples: number;
  precision: number;
  recall: number;
  f1: number;
  false_positives: number;
  normal_samples: number;
  data_type: string;
  limitation: string;
}
export interface Overview {
  assets: Asset[];
  episodes: Episode[];
  stats: {
    assets: number;
    healthy: number;
    attention: number;
    health: number | null;
    sensors: number;
    pending_reviews: number;
    open_orders: number;
  };
  trend: Reading[];
  trend_asset: string;
  model: ModelMetrics;
  mode: string;
}
export interface Operations {
  services: { name: string; status: string; detail: string }[];
  snapshots: number;
  api_p95_ms: number;
  requests_measured: number;
  model: ModelMetrics;
  limitations: string[];
}
export interface Preferences {
  compact: boolean;
  email_digest: boolean;
  display_timezone: string;
}
let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export class ApiError extends Error {
  readonly fields: Record<string, string>;
  constructor(message: string, fields: Record<string, string> = {}) {
    super(message);
    this.name = "ApiError";
    this.fields = fields;
  }
}

export function validationMessage(detail: unknown) {
  const fields: Record<string, string> = {};
  if (Array.isArray(detail)) {
    for (const issue of detail) {
      if (!issue || typeof issue.msg !== "string" || !Array.isArray(issue.loc)) continue;
      const field = issue.loc.find((part: unknown) => typeof part === "string" && part !== "body");
      if (typeof field === "string") fields[field] = issue.msg.replace(/^Value error,\s*/i, "");
    }
  }
  return {
    fields,
    message: typeof detail === "string" ? detail : Object.entries(fields).map(([field, message]) => `${field.replace(/_/g, " ")}: ${message}`).join(" ") || "Please check the form fields and try again.",
  };
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (options.method && options.method !== "GET") {
    // Recover the non-secret CSRF token after a development hot reload.
    if (!csrf && path !== "/auth/login") {
      const session = await fetch("/api/auth/me", {
        credentials: "same-origin",
      });
      if (session.ok) csrf = (await session.json()).csrf;
    }
    headers.set("X-CSRF-Token", csrf);
    headers.set(
      "Idempotency-Key",
      headers.get("Idempotency-Key") || crypto.randomUUID(),
    );
  }
  const response = await fetch("/api" + path, {
    credentials: "same-origin",
    ...options,
    headers,
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "The service is unavailable. Please retry." }));
    if (
      response.status === 401 &&
      path !== "/auth/login" &&
      path !== "/auth/me"
    )
      window.dispatchEvent(new Event("session-expired"));
    const validation = validationMessage(error.detail);
    throw new ApiError(validation.message, validation.fields);
  }
  return response.json() as Promise<T>;
}
export function post<T>(path: string, body: unknown) {
  return api<T>(path, { method: "POST", body: JSON.stringify(body) });
}
export function date(epoch: number, full = false) {
  return new Date(epoch * 1000).toLocaleString("en-GB", {
    timeZone: "Asia/Dubai",
    ...(full
      ? { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }
      : { hour: "2-digit", minute: "2-digit" }),
  });
}
export function age(epoch: number) {
  const min = Math.max(0, Math.floor((Date.now() / 1000 - epoch) / 60));
  return min < 1
    ? "Just now"
    : min < 60
      ? `${min}m ago`
      : min < 1440
        ? `${Math.floor(min / 60)}h ago`
        : `${Math.floor(min / 1440)}d ago`;
}
export function human(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (s) => s.toUpperCase());
}
