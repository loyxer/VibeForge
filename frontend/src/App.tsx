import { useEffect, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import Chat, { ChatMessage } from './components/Chat'
import Preview from './components/Preview'
import Gallery, { GallerySelection } from './components/Gallery'
import SignIn from './components/SignIn'
import SiteActions from './components/SiteActions'
import VersionHistory, { VersionSummary } from './components/VersionHistory'
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
  const [style, setStyle] = useState<string | null>(null)
  const [publishedUrl, setPublishedUrl] = useState<string | null>(null)
  const [publishedStale, setPublishedStale] = useState(false)
  const [publishBusy, setPublishBusy] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyVersion, setHistoryVersion] = useState(0)
  // An earlier version shown in the preview (nothing changes until Restore).
  const [viewing, setViewing] = useState<(VersionSummary & { html: string }) | null>(null)
  const [galleryVersion, setGalleryVersion] = useState(0)
  const [usage, setUsage] = useState<Usage | null>(null)

  useEffect(() => {
    apiFetch('/api/usage')
      .then((res) => (res.ok ? res.json() : null))
      .then(setUsage)
      .catch(() => setUsage(null))
  }, [])

  async function handleSend(prompt: string) {
    setViewing(null) // edits always build on the latest version
    setMessages((m) => [...m, { role: 'user', text: prompt }])
    setLoading(true)
    setProgress('Starting…')

    try {
      const post = (id: string | null) =>
        apiFetch('/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          // The style shapes a new site; edits keep the site's own look.
          body: JSON.stringify({ prompt, project_id: id, style: id ? null : style }),
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
          if (event.project_id !== projectId) {
            setPublishedUrl(null) // a brand-new site isn't published yet
            setPublishedStale(false)
          } else {
            // A published site keeps showing the old version until re-published.
            setPublishedStale(publishedUrl !== null)
          }
          setProjectId(event.project_id)
          setUsage((u) => (u ? { ...u, remaining_today: event.remaining_today } : u))
        }
      }
      if (!finished) throw new Error('The connection was interrupted — please try again.')

      setMessages((m) => [...m, { role: 'assistant', text: 'Done — updated the preview.' }])
      setGalleryVersion((v) => v + 1)
      setHistoryVersion((v) => v + 1)
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
    setPublishedUrl(selection.publishedUrl)
    setPublishedStale(false)
    setViewing(null)
    setMessages(
      selection.history.flatMap((prompt) => [
        { role: 'user' as const, text: prompt },
        { role: 'assistant' as const, text: 'Done — updated the preview.' },
      ]),
    )
  }

  function handleNewSite() {
    setProjectId(null)
    setHtml(null)
    setMessages([])
    setPublishedUrl(null)
    setPublishedStale(false)
    setViewing(null)
    setHistoryOpen(false)
  }

  async function handleViewVersion(version: VersionSummary) {
    if (!projectId) return
    const res = await apiFetch(`/api/projects/${projectId}/versions/${version.id}`)
    if (!res.ok) return
    const data = await res.json()
    setViewing({ ...version, html: data.html })
  }

  async function handleRestore() {
    if (!projectId || !viewing) return
    const res = await apiFetch(`/api/projects/${projectId}/versions/${viewing.id}/restore`, {
      method: 'POST',
    })
    if (!res.ok) {
      setMessages((m) => [...m, { role: 'assistant', text: 'Error: could not restore that version.' }])
      return
    }
    const data = await res.json()
    setHtml(data.html)
    setMessages((m) => [
      ...m,
      { role: 'user', text: data.history[data.history.length - 1] },
      { role: 'assistant', text: 'Done — that version is back.' },
    ])
    setViewing(null)
    setHistoryVersion((v) => v + 1)
    setGalleryVersion((v) => v + 1)
    setPublishedStale(publishedUrl !== null)
  }

  async function changePublished(method: 'POST' | 'DELETE') {
    if (!projectId) return
    setPublishBusy(true)
    try {
      const res = await apiFetch(`/api/projects/${projectId}/publish`, { method })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.detail ?? `Server error: ${res.status}`)
      setPublishedUrl(data.published_url)
      setPublishedStale(false)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Something went wrong'
      setMessages((m) => [...m, { role: 'assistant', text: `Error: ${message}` }])
    } finally {
      setPublishBusy(false)
    }
  }

  function handleGalleryDelete(deletedId: string) {
    if (deletedId === projectId) handleNewSite()
  }

  // Built from the HTML already on screen: a plain link to the backend
  // couldn't carry the sign-in token.
  function handleDownload() {
    const shown = viewing?.html ?? html // whichever version is on screen
    if (!shown) return
    const url = URL.createObjectURL(new Blob([shown], { type: 'text/html' }))
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
          isNewSite={projectId === null}
          style={style}
          onStyleChange={setStyle}
          onNewSite={handleNewSite}
          onSend={handleSend}
        />
        <Gallery
          refreshKey={galleryVersion}
          onSelect={handleGallerySelect}
          onDelete={handleGalleryDelete}
        />
      </div>
      <div>
        {viewing && (
          <div className="viewing">
            <span>
              Viewing version {viewing.number}
              {viewing.prompt && <> · “{viewing.prompt}”</>}
            </span>
            <button type="button" className="viewing__restore" onClick={handleRestore}>
              Restore this version
            </button>
            <button type="button" onClick={() => setViewing(null)}>
              Back to latest
            </button>
          </div>
        )}
        <Preview html={viewing?.html ?? html} building={loading} liveCode={liveCode} />
        {html && !loading && projectId && (
          <SiteActions
            publishedUrl={publishedUrl}
            stale={publishedStale}
            busy={publishBusy}
            historyOpen={historyOpen}
            onToggleHistory={() => setHistoryOpen((open) => !open)}
            onDownload={handleDownload}
            onPublish={() => changePublished('POST')}
            onUnpublish={() => changePublished('DELETE')}
          />
        )}
        {historyOpen && projectId && !loading && (
          <VersionHistory
            projectId={projectId}
            refreshKey={historyVersion}
            viewingId={viewing?.id ?? null}
            onView={handleViewVersion}
          />
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
