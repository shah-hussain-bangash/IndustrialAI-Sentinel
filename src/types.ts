import type {
  Overview,
  Asset,
  Episode,
  Investigation,
  WorkOrder,
  DocumentInfo,
  AuditEvent,
  Operations,
} from "./api";
export type Page =
  | "overview"
  | "assets"
  | "monitor"
  | "sensors"
  | "intelligence"
  | "knowledge"
  | "reliability"
  | "orders"
  | "activity"
  | "settings"
  | "production"
  | "organization";
export interface Data {
  overview: Overview;
  assets: Asset[];
  episodes: Episode[];
  investigations: Investigation[];
  orders: WorkOrder[];
  documents: DocumentInfo[];
  activity: AuditEvent[];
  operations: Operations;
}
export type Run = (
  action: () => Promise<unknown>,
  success: string,
) => Promise<boolean>;
