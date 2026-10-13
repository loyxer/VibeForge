import { useEffect, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import Chat, { ChatMessage } from './components/Chat'
import Preview from './components/Preview'
import Gallery, { GallerySelection } from './components/Gallery'
import SignIn from './components/SignIn'
import { Privacy, Terms } from './components/Legal'
import { apiFetch, readEvents, Usage } from './api'
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

  const path = window.location.pathname

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

      {/* No router: the only other pages are the two static legal ones. */}
      {path === '/privacy' ? (
        <Privacy />
      ) : path === '/terms' ? (
        <Terms />
      ) : !authReady ? null : supabase && !session ? (
        <SignIn />
      ) : (
        // Keyed by user so signing in as someone else starts from a clean slate.
        <Workspace key={session?.user.id ?? 'local'} />
      )}

      <footer>
        <a href="/privacy">Privacy</a>
        <a href="/terms">Terms</a>
      </footer>
    </div>
  )
}

function Workspace() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [html, setHtml] = useState<string | null>(null)
  const [projectId, setProjectId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState<string | null>(null)
  const [liveCode, setLiveCode] = useState('')
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
    setProgress('Starting…')

    try {
      const post = (id: string | null) =>
        apiFetch('/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt, project_id: id }),
        })

      let res = await post(projectId)
      if (res.status === 404 && projectId) {
        // The backend lost this project (e.g. it was deleted in another
        // tab) but we still remember its id — start a fresh one instead
        // of failing on an edit the server can no longer make sense of.
        res = await post(null)
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail ?? `Server error: ${res.status}`)
      }

      // The site arrives in pieces: repaint the preview every so often with
      // what's been written so far, then swap in the final version.
      let written = ''
      let lastPaint = 0
      let lastCode = 0
      let finished = false
      for await (const event of readEvents(res)) {
        if (event.type === 'status') {
          setProgress(event.text)
        } else if (event.type === 'reset') {
          // The model dropped out halfway; another one starts from scratch.
          written = ''
          setLiveCode('')
        } else if (event.type === 'text') {
          written += event.text
          setProgress(`Writing your site… ${Math.round(written.length / 1024)} KB`)
          if (Date.now() - lastCode > 150) {
            lastCode = Date.now()
            setLiveCode(written.slice(-1500))
          }
          // Repainting reloads fonts and images, so not too often; the
          // preview keeps showing the last version until the next is ready.
          const partial = partialPage(written)
          if (partial && Date.now() - lastPaint > 1500) {
            lastPaint = Date.now()
            setHtml(partial)
          }
        } else if (event.type === 'error') {
          throw new Error(event.detail)
        } else if (event.type === 'done') {
          finished = true
          setHtml(event.html)
          setProjectId(event.project_id)
          setUsage((u) => (u ? { ...u, remaining_today: event.remaining_today } : u))
        }
      }
      if (!finished) throw new Error('The connection was interrupted — please try again.')

      setMessages((m) => [...m, { role: 'assistant', text: 'Done — updated the preview.' }])
      setGalleryVersion((v) => v + 1)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Generation failed'
      setMessages((m) => [...m, { role: 'assistant', text: `Error: ${message}` }])
    } finally {
      setLoading(false)
      setProgress(null)
      setLiveCode('')
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
        <Chat
          messages={messages}
          loading={loading}
          progress={progress}
          usage={usage}
          onSend={handleSend}
        />
        <Gallery
          refreshKey={galleryVersion}
          onSelect={handleGallerySelect}
          onDelete={handleGalleryDelete}
        />
      </div>
      <div>
        <Preview html={html} building={loading} liveCode={liveCode} />
        {html && !loading && (
          <button type="button" className="download-link" onClick={handleDownload}>
            Download HTML
          </button>
        )}
      </div>
    </main>
  )
}

// What's been streamed so far, if it's far enough along to be worth showing:
// once the <body> has started, browsers render a half-written page fine.
function partialPage(written: string): string | null {
  const text = written.replace(/^\s*```[a-zA-Z]*\n?/, '')
  return /<body[\s>]/i.test(text) ? text : null
}
