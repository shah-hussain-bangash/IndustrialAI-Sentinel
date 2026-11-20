export interface AlignmentFrame {
  ready: boolean;
  rows: { channel: string; event: null | { observed_at: number } }[];
}
export interface SensorWindow {
  channel: string;
  stale_after_seconds: number;
}
export function alignmentWindow(
  frame: AlignmentFrame | null,
  sensors: SensorWindow[],
  now: number,
) {
  if (!frame || frame.rows.length !== 4)
    return { expiresAt: null, remaining: 0, eligible: false };
  const limits = frame.rows.map((row) => {
    const sensor = sensors.find((sensor) => sensor.channel === row.channel);
    return row.event &&
      sensor &&
      Number.isFinite(row.event.observed_at) &&
      Number.isFinite(sensor.stale_after_seconds)
      ? row.event.observed_at + sensor.stale_after_seconds
      : null;
  });
  if (limits.some((limit) => limit === null))
    return { expiresAt: null, remaining: 0, eligible: false };
  const expiresAt = Math.min(...(limits as number[]));
  return {
    expiresAt,
    remaining: Math.max(0, Math.floor(expiresAt - now)),
    eligible: frame.ready && now < expiresAt,
  };
}
export function duration(seconds: number) {
  const safe = Math.max(0, Math.floor(seconds));
  return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, "0")}`;
}
export function signalSource(source: string) {
  if (source.startsWith("gateway:")) return "Gateway sender";
  if (source === "manual-alignment-ui") return "Manual test frame";
  if (source === "quarantine-review") return "Reviewed correction";
  return source || "Unspecified source";
}
