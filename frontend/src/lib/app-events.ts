/** Browser-only: notify Settings / Usage listeners to refresh plan quota from the backend. */

export const PLAN_USAGE_CHANGED_EVENT = "alphalens-plan-usage-changed";

export function emitPlanUsageChanged(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(PLAN_USAGE_CHANGED_EVENT));
}
