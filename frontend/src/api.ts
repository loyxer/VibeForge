// In local dev this is empty, so requests go to "/api/..." and Vite's
// dev-server proxy (vite.config.ts) forwards them to localhost:8000. In
// production there's no such proxy, so the build needs to know the real
// deployed backend URL — set via the VITE_API_URL env var at build time.
export const API_BASE = import.meta.env.VITE_API_URL ?? ''

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`
}
