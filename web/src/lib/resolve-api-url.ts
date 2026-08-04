// Local dev runs the frontend on :3000 and the API on :8000, so
// NEXT_PUBLIC_API_URL must be set explicitly. In production, nginx
// proxies /api/ and /ws/ on the same origin as the frontend, so no
// configuration is needed there — window.location.origin is correct.
export function resolveApiUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  if (typeof window !== "undefined") {
    return window.location.origin;
  }
  return "http://localhost:8000";
}

export function resolveWsUrl(): string {
  const apiUrl = resolveApiUrl();
  return apiUrl.replace(/^http/, "ws");
}
