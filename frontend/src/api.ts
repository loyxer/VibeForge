import { supabase } from './supabase'

// In local dev this is empty, so requests go to "/api/..." and Vite's
// dev-server proxy (vite.config.ts) forwards them to localhost:8000. In
// production there's no such proxy, so the build needs to know the real
// deployed backend URL — set via the VITE_API_URL env var at build time.
const API_BASE = import.meta.env.VITE_API_URL ?? ''

function apiUrl(path: string): string {
  return `${API_BASE}${path}`
}

// fetch() that also sends the signed-in user's session token, which the
// backend needs to know whose projects to read and write.
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  if (supabase) {
    const { data } = await supabase.auth.getSession()
    if (data.session) headers.set('Authorization', `Bearer ${data.session.access_token}`)
  }
  return fetch(apiUrl(path), { ...init, headers })
}

// Daily generation allowance; nulls mean "no limit".
export type Usage = { limit: number | null; remaining_today: number | null }

// What POST /api/generate streams back, one JSON object per line.
export type GenerationEvent =
  | { type: 'status' | 'model' | 'text' | 'reset'; text: string }
  | { type: 'done'; project_id: string; html: string; remaining_today: number | null }
  | { type: 'error'; status: number; detail: string }

export async function* readEvents(res: Response): AsyncGenerator<GenerationEvent> {
  const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    const lines = buffer.split('\n')
    buffer = lines.pop()! // the last piece may be an unfinished line
    for (const line of lines) if (line.trim()) yield JSON.parse(line)
  }
  if (buffer.trim()) yield JSON.parse(buffer)
}
