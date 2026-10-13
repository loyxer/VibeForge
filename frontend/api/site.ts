// Serves a published site at /s/<slug> (vercel.json rewrites it here).
// Runs on Vercel rather than our Render backend so a shared link opens
// instantly instead of waiting ~50 s for Render to wake up. It reads the
// page straight from Supabase with the public key, which may only see a
// page's slug and HTML (see backend/supabase/schema.sql).

const SUPABASE_URL = process.env.VITE_SUPABASE_URL
const SUPABASE_KEY = process.env.VITE_SUPABASE_PUBLISHABLE_KEY

// The page was written by an AI: serve it in a sandbox, so its scripts get
// a unique origin and can't touch anything else on this domain — above all
// the VibeForge app's sign-in session. Keep in sync with SANDBOX_CSP in
// backend/app/publishing.py.
const SANDBOX_CSP = 'sandbox allow-scripts allow-forms allow-popups allow-modals'

export async function GET(request: Request): Promise<Response> {
  const slug = new URL(request.url).searchParams.get('slug') ?? ''
  if (!/^[a-z0-9]{8}$/.test(slug) || !SUPABASE_URL || !SUPABASE_KEY) return notFound()

  const res = await fetch(
    `${SUPABASE_URL}/rest/v1/published_sites?slug=eq.${slug}&select=html`,
    { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } },
  )
  if (!res.ok) return new Response('Something went wrong — try again later.', { status: 502 })
  const rows = (await res.json()) as { html: string }[]
  if (rows.length === 0) return notFound()

  return new Response(rows[0].html, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Content-Security-Policy': SANDBOX_CSP,
      // Re-publishing shows up within a minute without hitting the
      // database on every visit.
      'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=300',
      // Generated pages shouldn't end up in search results under our name.
      'X-Robots-Tag': 'noindex',
    },
  })
}

function notFound(): Response {
  return new Response(
    `<!doctype html><meta charset="utf-8"><title>Not found</title>
<body style="font-family:system-ui;display:grid;place-items:center;height:100vh;margin:0;background:#12141a;color:#9a9ea8">
<p>This page doesn't exist or was unpublished. <a style="color:#9fb8f0" href="/">Make your own with VibeForge</a></p>`,
    { status: 404, headers: { 'Content-Type': 'text/html; charset=utf-8' } },
  )
}
