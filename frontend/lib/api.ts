// lib/api.ts — the single place for frontend API token + header requirements.
//
// The JWT needs to be handled in two different layers:
//   1. Client → Next.js route (pages/components): apiFetch() obtains the token
//      via /api/auth/token and adds Authorization (+ Content-Type for JSON).
//   2. Next.js route → Python backend (server proxy): proxyAuthHeaders()
//      forwards the incoming Authorization header.
//
// Full migration checklist:
//   /home/rono/Documents/workbench-documents/workbench-UI-api-token-plan.html

// getToken fetches the user's JWT from /api/auth/token (NextAuth session).
// Fetch-per-call is the safe default — JWTs expire, so nothing is cached across
// requests. (A short-TTL cache is a possible later optimisation.)
async function getToken(): Promise<string> {
  const res = await fetch("/api/auth/token", { credentials: "include" });
  if (!res.ok) {
    throw new Error("Unauthorized");
  }
  const data = await res.json();
  if (!data.token) {
    throw new Error("No token in response");
  }
  return data.token;
}

// apiFetch wraps fetch for client-side API calls: it adds the Authorization
// header and Content-Type for JSON bodies. Pass { auth: false } for public
// endpoints that must not send a token (login, register, features, languages,
// health, version, …).
export async function apiFetch(
  url: string,
  options: RequestInit & { auth?: boolean } = {},
): Promise<Response> {
  const { auth = true, headers, body, ...rest } = options;

  const finalHeaders = new Headers(headers);
  if (auth) {
    finalHeaders.set("Authorization", `Bearer ${await getToken()}`);
  }
  if (body != null && !finalHeaders.has("Content-Type")) {
    finalHeaders.set("Content-Type", "application/json");
  }

  return fetch(url, { ...rest, body, headers: finalHeaders });
}

// proxyAuthHeaders returns the headers a Next.js route handler should send when
// proxying a request to the Python backend: the incoming Authorization header
// plus the JSON content type.
export function proxyAuthHeaders(req: Request): Record<string, string> {
  return {
    "Content-Type": "application/json",
    Authorization: req.headers.get("Authorization") || "",
  };
}
