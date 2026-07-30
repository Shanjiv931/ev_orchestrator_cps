export const STALE_VERIFICATION_THRESHOLD_HOURS = 6;

export function safetyColor(score: number): string {
  if (score >= 0.7) return "#16a34a";
  if (score >= 0.4) return "#f59e0b";
  return "#dc2626";
}

export function isStaleVerification(staleness_hours: number): boolean {
  return staleness_hours > STALE_VERIFICATION_THRESHOLD_HOURS;
}

/** Tailwind classes for a safety-score badge with a text/background pair
 * that keeps readable contrast in both light and dark mode - a plain pale
 * background (e.g. bg-green-100) inherits dark-mode's light body text
 * color and becomes nearly invisible, so text color is set explicitly
 * alongside each background rather than left to inherit. */
export function safetyBadgeClasses(score: number): string {
  if (score >= 0.7) {
    return "bg-green-100 text-green-900 dark:bg-green-900 dark:text-green-100";
  }
  if (score >= 0.4) {
    return "bg-amber-100 text-amber-900 dark:bg-amber-900 dark:text-amber-100";
  }
  return "bg-red-100 text-red-900 dark:bg-red-900 dark:text-red-100";
}
