import { useEffect, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import Chat, { ChatMessage } from './components/Chat'
import Preview from './components/Preview'
import Gallery, { GallerySelection } from './components/Gallery'
import SignIn from './components/SignIn'
import { apiFetch, Usage } from './api'
import { supabase } from './supabase'

export default function App() {
  const [session, setSession] = useState<Session | null>(null)
  // Without Supabase configured there are no accounts, so nothing to wait for.
  const [authReady, setAuthReady] = useState(!supabase)

  useEffect(() => {
    if (!supabase) return
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setAuthReady(true)
    })
    const { data } = supabase.auth.onAuthStateChange((_event, s) => setSession(s))
    return () => data.subscription.unsubscribe()
  }, [])

  return (
    <div className="app">
      <header>
        <div>
          <h1>VibeForge</h1>
          <p>Describe a site in plain words — watch it build, live.</p>
        </div>
        {session && (
          <div className="account">
            <span className="account__email">{session.user.email}</span>
            <button type="button" onClick={() => supabase?.auth.signOut()}>
              Sign out
            </button>
          </div>
        )}
      </header>

      {!authReady ? null : supabase && !session ? (
        <SignIn />
      ) : (
        // Keyed by user so signing in as someone else starts from a clean slate.
        <Workspace key={session?.user.id ?? 'local'} />
      )}
    </div>
  )
}

function Workspace() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [html, setHtml] = useState<string | null>(null)
  const [projectId, setProjectId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [galleryVersion, setGalleryVersion] = useState(0)
  const [usage, setUsage] = useState<Usage | null>(null)

  useEffect(() => {
    apiFetch('/api/usage')
      .then((res) => (res.ok ? res.json() : null))
      .then(setUsage)
      .catch(() => setUsage(null))
  }, [])

  async function handleSend(prompt: string) {
    setMessages((m) => [...m, { role: 'user', text: prompt }])
    setLoading(true)

    try {
      const post = (id: string | null) =>
        apiFetch('/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt, project_id: id }),
        })

      let res = await post(projectId)
      let data = await res.json()

      if (res.status === 404 && projectId) {
        // The backend lost this project (e.g. a free-tier restart wiped its
        // storage) but we still remember its id — start a fresh one instead
        // of failing on an edit the server can no longer make sense of.
        res = await post(null)
        data = await res.json()
      }

      if (!res.ok) throw new Error(data.detail ?? `Server error: ${res.status}`)

      setHtml(data.html)
      setProjectId(data.project_id)
      setUsage((u) => (u ? { ...u, remaining_today: data.remaining_today } : u))
      setMessages((m) => [...m, { role: 'assistant', text: 'Done — updated the preview.' }])
      setGalleryVersion((v) => v + 1)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Generation failed'
      setMessages((m) => [...m, { role: 'assistant', text: `Error: ${message}` }])
    } finally {
      setLoading(false)
    }
  }

  function handleGallerySelect(selection: GallerySelection) {
    setProjectId(selection.projectId)
    setHtml(selection.html)
    setMessages(
      selection.history.flatMap((prompt) => [
        { role: 'user' as const, text: prompt },
        { role: 'assistant' as const, text: 'Done — updated the preview.' },
      ]),
    )
  }

  function handleGalleryDelete(deletedId: string) {
    if (deletedId === projectId) {
      setProjectId(null)
      setHtml(null)
      setMessages([])
    }
  }

  // Built from the HTML already on screen: a plain link to the backend
  // couldn't carry the sign-in token.
  function handleDownload() {
    if (!html) return
    const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `${projectId ?? 'site'}.html`
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <main>
      <div className="sidebar">
        <Chat messages={messages} loading={loading} usage={usage} onSend={handleSend} />
        <Gallery
          refreshKey={galleryVersion}
          onSelect={handleGallerySelect}
          onDelete={handleGalleryDelete}
        />
      </div>
      <div>
        <Preview html={html} />
        {html && (
          <button type="button" className="download-link" onClick={handleDownload}>
            Download HTML
          </button>
        )}
      </div>
    </main>
  )
}
