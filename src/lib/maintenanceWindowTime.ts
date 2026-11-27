export function gstWindowTime(value: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/.test(value)) return null;
  const seconds = new Date(value + "+04:00").getTime() / 1000;
  const normalized = value.length === 16 ? value + ":00" : value;
  return Number.isFinite(seconds) && seconds >= 0 && seconds <= 4102444800 && gstWindowInput(seconds) === normalized ? seconds : null;
}
export function gstWindowInput(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0 || seconds > 4102444800) return "";
  return new Date((seconds + 14400) * 1000).toISOString().slice(0, 19);
}
export function validWindowRange(start: number | null, end: number | null): boolean {
  return start !== null && end !== null && end > start && end - start <= 604800;
}
