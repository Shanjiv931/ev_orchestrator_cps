export const STALE_VERIFICATION_THRESHOLD_HOURS = 6;

export function safetyColor(score: number): string {
  if (score >= 0.7) return "#16a34a";
  if (score >= 0.4) return "#f59e0b";
  return "#dc2626";
}

export function isStaleVerification(staleness_hours: number): boolean {
  return staleness_hours > STALE_VERIFICATION_THRESHOLD_HOURS;
}
