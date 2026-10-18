// /sitemap.xml (vercel.json rewrites it here): the published sites whose
// owners allowed search engines to list them. Public data only — the same
// anon key and columns as api/site.ts.

const SUPABASE_URL = process.env.VITE_SUPABASE_URL
const SUPABASE_KEY = process.env.VITE_SUPABASE_PUBLISHABLE_KEY

export async function GET(request: Request): Promise<Response> {
  const origin = new URL(request.url).origin
  let rows: { slug: string; published_at: string }[] = []
  if (SUPABASE_URL && SUPABASE_KEY) {
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/published_sites?indexable=eq.true&select=slug,published_at&order=published_at.desc&limit=5000`,
      { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } },
    )
    if (!res.ok) return new Response('Something went wrong — try again later.', { status: 502 })
    rows = await res.json()
  }
  const urls = rows
    .filter((r) => /^[a-z0-9]{8}$/.test(r.slug))
    .map((r) => `<url><loc>${origin}/s/${r.slug}</loc><lastmod>${r.published_at.slice(0, 10)}</lastmod></url>`)
    .join('')
  return new Response(
    `<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${urls}</urlset>`,
    {
      headers: {
        'Content-Type': 'application/xml; charset=utf-8',
        'Cache-Control': 'public, s-maxage=3600, stale-while-revalidate=86400',
      },
    },
  )
}
