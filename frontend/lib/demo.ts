/**
 * Demo-mode detection helper.
 *
 * Answers whether the running system is in demo mode by probing the public
 * settings endpoint. Centralising this here (instead of each page re-fetching
 * `/api/public-settings` and re-parsing `demoMode`) gives one source of truth
 * for "is this the demo system?".
 *
 * Returns `false` on any failure (unreachable backend, non-JSON response), so
 * callers treat an unknown state as "not demo".
 */
export async function isDemoSystem(): Promise<boolean> {
  try {
    const res = await fetch("/api/public-settings");
    if (!res.ok) return false;
    const data = await res.json();
    return data.demoMode === true;
  } catch {
    return false;
  }
}
