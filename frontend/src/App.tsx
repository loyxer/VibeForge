import { ReactNode, useEffect, useRef, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import Chat, { ChatMessage, Progress } from './components/Chat'
import Preview, { Device, PreviewHandle } from './components/Preview'
import Gallery, { GallerySelection } from './components/Gallery'
import SignIn from './components/SignIn'
import SiteActions from './components/SiteActions'
import VersionHistory, { VersionSummary } from './components/VersionHistory'
import { Privacy, Terms } from './components/Legal'
import TopBar from './components/TopBar'
import Stats from './components/Stats'
import EditToolbar from './components/EditToolbar'
import Review from './components/Review'
import ReviewPanel from './components/ReviewPanel'
import type { Selection, SiteLanguages } from './textEditor'
import { apiFetch, readEvents, Usage } from './api'
import { discardPhoto, MAX_PHOTOS_PER_SITE, shrink, TrayPhoto, uploadPhoto } from './photoUpload'
import { supabase } from './supabase'
import { useT } from './i18n'

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

  // No router: the only other pages are the two static legal ones.
  if (path === '/privacy' || path === '/terms') {
    return <Shell session={session}>{path === '/privacy' ? <Privacy /> : <Terms />}</Shell>
  }
  // A client opens the review link without an account.
  const review = /^\/r\/([\w-]{1,40})\/?$/.exec(path)
  if (review) {
    return (
      <Shell session={session} workspace>
        <Review token={review[1]} />
      </Shell>
    )
  }
  if (!authReady) return <Shell session={null} />
  if (supabase && !session) {
    return (
      <Shell session={null}>
        <SignIn />
      </Shell>
    )
  }
  if (path === '/stats') {
    return (
      <Shell session={session}>
        <Stats />
      </Shell>
    )
  }
  // Keyed by user so signing in as someone else starts from a clean slate.
  return <Workspace key={session?.user.id ?? 'local'} session={session} />
}

type ShellProps = {
  session: Session | null
  workspace?: boolean
  usage?: Usage | null
  onOpenGallery?: () => void
  children?: ReactNode
}

function Shell({ session, workspace, usage, onOpenGallery, children }: ShellProps) {
  const t = useT()
  return (
    <div className={workspace ? 'app app--workspace' : 'app'}>
      <TopBar session={session} usage={usage ?? null} onOpenGallery={onOpenGallery} />
      {children}
      <footer className="footer">
        <a href="/privacy">{t('footer.privacy')}</a>
        <a href="/terms">{t('footer.terms')}</a>
        <a href="https://unsplash.com/?utm_source=vibeforge&utm_medium=referral" target="_blank" rel="noopener">
          {t('footer.unsplash')}
        </a>
      </footer>
    </div>
  )
}

function Workspace({ session }: { session: Session | null }) {
  const t = useT()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [html, setHtml] = useState<string | null>(null)
  const [projectId, setProjectId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState<Progress | null>(null)
  const [liveCode, setLiveCode] = useState('')
  const [style, setStyle] = useState<string | null>(null)
  // Ukrainian + English with a switcher; asked for before a new site is made.
  const [bilingual, setBilingual] = useState(false)
  const [publishedUrl, setPublishedUrl] = useState<string | null>(null)
  const [publishedStale, setPublishedStale] = useState(false)
  const [publishBusy, setPublishBusy] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyVersion, setHistoryVersion] = useState(0)
  // An earlier version shown in the preview (nothing changes until Restore).
  const [viewing, setViewing] = useState<(VersionSummary & { html: string }) | null>(null)
  // Editing the text by hand in the preview (no AI).
  const [editing, setEditing] = useState(false)
  const [savingEdit, setSavingEdit] = useState(false)
  const preview = useRef<PreviewHandle>(null)
  // What was clicked in the preview while editing, and the photos uploaded for it.
  const [selection, setSelection] = useState<Selection | null>(null)
  const [editLangs, setEditLangs] = useState<SiteLanguages | null>(null)
  const [editPhotos, setEditPhotos] = useState<{ id: string; url: string }[]>([])
  const [galleryOpen, setGalleryOpen] = useState(false)
  const [projectName, setProjectName] = useState<string | null>(null)
  const [usage, setUsage] = useState<Usage | null>(null)
  // The person's own photos waiting to go out with the next message.
  const [tray, setTray] = useState<TrayPhoto[]>([])
  const [device, setDevice] = useState<Device>('desktop')
  // Is the VibeForge bot set up, and has this person connected it?
  const [telegram, setTelegram] = useState<{ available: boolean; connected: boolean } | null>(null)

  // Checked again on coming back to the tab — e.g. from pressing Start in Telegram.
  useEffect(() => {
    const load = () =>
      apiFetch('/api/telegram')
        .then((res) => (res.ok ? res.json() : null))
        .then(setTelegram)
        .catch(() => {})
    load()
    window.addEventListener('focus', load)
    return () => window.removeEventListener('focus', load)
  }, [])

  useEffect(() => {
    apiFetch('/api/usage')
      .then((res) => (res.ok ? res.json() : null))
      .then(setUsage)
      .catch(() => setUsage(null))
  }, [])

  // Errors we raise ourselves carry a dictionary key; the server's come as
  // English text. Chat shows either in the current language.
  const fail = (err: unknown, fallback: 'error.generation' | 'error.save' | 'error.generic') =>
    setMessages((m) => [
      ...m,
      { role: 'assistant', error: err instanceof Error && err.message ? err.message : fallback },
    ])

  const updateTray = (key: string, change: Partial<TrayPhoto>) =>
    setTray((all) => all.map((p) => (p.key === key ? { ...p, ...change } : p)))

  function handleAddPhotos(files: File[]) {
    const room = MAX_PHOTOS_PER_SITE - tray.length
    for (const file of files.slice(0, Math.max(room, 0))) {
      const key = crypto.randomUUID()
      setTray((all) => [...all, { key, preview: URL.createObjectURL(file), status: 'uploading' }])
      shrink(file)
        .then((blob) => {
          updateTray(key, { preview: URL.createObjectURL(blob) })
          return uploadPhoto(blob, projectId)
        })
        .then(({ id }) => updateTray(key, { status: 'ready', id }))
        .catch((err) => updateTray(key, { status: 'error', error: err instanceof Error ? err.message : 'error.generic' }))
    }
  }

  function handleRemovePhoto(key: string) {
    const photo = tray.find((p) => p.key === key)
    if (photo?.id) discardPhoto(photo.id)
    if (photo) URL.revokeObjectURL(photo.preview)
    setTray((all) => all.filter((p) => p.key !== key))
  }

  // sent: the photos went out with a message, so they're on the site now.
  function clearTray(sent: boolean) {
    for (const photo of tray) {
      if (!sent && photo.id) discardPhoto(photo.id)
      URL.revokeObjectURL(photo.preview)
    }
    setTray([])
  }

  async function handleSend(prompt: string, makeBilingual = false) {
    setViewing(null) // edits always build on the latest version
    const photoIds = tray.flatMap((p) => (p.status === 'ready' && p.id ? [p.id] : []))
    setMessages((m) => [...m, { role: 'user', text: prompt, photos: photoIds.length }])
    setLoading(true)
    setProgress({ text: 'progress.starting' })

    try {
      const post = (id: string | null) =>
        apiFetch('/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          // The style shapes a new site; edits keep the site's own look.
          body: JSON.stringify({
            prompt,
            project_id: id,
            style: id ? null : style,
            photo_ids: photoIds,
            bilingual: id ? makeBilingual : bilingual,
          }),
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
        throw new Error(data.detail ?? t('error.server', { status: res.status }))
      }

      // The site arrives in pieces: repaint the preview every so often with
      // what's been written so far, then swap in the final version.
      let written = ''
      let lastPaint = 0
      let lastCode = 0
      let finished = false
      let unusedPhotos: number[] = []
      for await (const event of readEvents(res)) {
        if (event.type === 'status') {
          setProgress({ text: event.text })
        } else if (event.type === 'reset') {
          // The model dropped out halfway; another one starts from scratch.
          written = ''
          setLiveCode('')
        } else if (event.type === 'text') {
          written += event.text
          setProgress({ text: 'progress.writing', params: { kb: Math.round(written.length / 1024) } })
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
          unusedPhotos = event.unused_photos ?? []
        }
      }
      if (!finished) throw new Error('error.interrupted')

      clearTray(true)
      setMessages((m) => [
        ...m,
        { role: 'assistant', key: 'reply.done' },
        ...(unusedPhotos.length
          ? [{ role: 'assistant' as const, key: 'photos.unused' as const, params: { list: unusedPhotos.join(', ') } }]
          : []),
      ])
      setHistoryVersion((v) => v + 1)
    } catch (err) {
      fail(err, 'error.generation')
    } finally {
      setLoading(false)
      setProgress(null)
      setLiveCode('')
    }
  }

  function handleGallerySelect(selection: GallerySelection) {
    setGalleryOpen(false)
    clearTray(false)
    setProjectName(selection.name)
    setProjectId(selection.projectId)
    setHtml(selection.html)
    setPublishedUrl(selection.publishedUrl)
    setPublishedStale(false)
    setViewing(null)
    stopEditing()
    setHistoryOpen(false)
    setMessages(
      selection.history.flatMap((prompt) => [
        { role: 'user' as const, text: prompt },
        { role: 'assistant' as const, key: 'reply.doneEarlier' as const },
      ]),
    )
  }

  function handleNewSite() {
    clearTray(false)
    setProjectName(null)
    setProjectId(null)
    setHtml(null)
    setMessages([])
    setPublishedUrl(null)
    setPublishedStale(false)
    setViewing(null)
    setHistoryOpen(false)
    stopEditing()
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
      setMessages((m) => [...m, { role: 'assistant', error: 'error.restore' }])
      return
    }
    const data = await res.json()
    setHtml(data.html)
    setMessages((m) => [
      ...m,
      { role: 'user', text: data.history[data.history.length - 1] },
      { role: 'assistant', key: 'reply.restored' },
    ])
    setViewing(null)
    setHistoryVersion((v) => v + 1)
    setPublishedStale(publishedUrl !== null)
  }

  function stopEditing() {
    setEditing(false)
    setSelection(null)
    setEditLangs(null)
    setEditPhotos([])
  }

  async function handleSaveEdit() {
    if (!projectId || !preview.current) return
    setSavingEdit(true)
    try {
      const edited = await preview.current.getEditedHtml()
      // Only photos that ended up on the page (not ones replaced again).
      const photoIds = editPhotos.filter((p) => edited.includes(p.url)).map((p) => p.id)
      const res = await apiFetch(`/api/projects/${projectId}/text-edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ html: edited, photo_ids: photoIds }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.detail ?? t('error.server', { status: res.status }))
      setHtml(data.html)
      setMessages((m) => [
        ...m,
        { role: 'user', text: data.history[data.history.length - 1] },
        { role: 'assistant', key: 'reply.saved' },
      ])
      stopEditing()
      setHistoryVersion((v) => v + 1)
      setPublishedStale(publishedUrl !== null)
    } catch (err) {
      fail(err, 'error.save')
    } finally {
      setSavingEdit(false)
    }
  }

  async function changePublished(method: 'POST' | 'DELETE') {
    if (!projectId) return
    setPublishBusy(true)
    try {
      const res = await apiFetch(`/api/projects/${projectId}/publish`, { method })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.detail ?? t('error.server', { status: res.status }))
      setPublishedUrl(data.published_url)
      setPublishedStale(false)
    } catch (err) {
      fail(err, 'error.generic')
    } finally {
      setPublishBusy(false)
    }
  }

  function handleGalleryRename(renamedId: string, name: string | null) {
    if (renamedId === projectId) setProjectName(name)
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

  // A site is called by the name its owner gave it, else by its first request.
  const firstPrompt = messages.find((m) => m.role === 'user')
  const title =
    projectId && projectName
      ? projectName
      : projectId && firstPrompt && 'text' in firstPrompt
        ? firstPrompt.text
        : t('chat.newSite')

  return (
    <Shell session={session} workspace usage={usage} onOpenGallery={() => setGalleryOpen(true)}>
      <main className="workspace">
        <Chat
          title={title}
          messages={messages}
          loading={loading}
          progress={progress}
          usage={usage}
          isNewSite={projectId === null}
          paused={editing}
          style={style}
          onStyleChange={setStyle}
          bilingual={bilingual}
          onBilingualChange={setBilingual}
          onNewSite={handleNewSite}
          onSend={handleSend}
          tray={tray}
          onAddPhotos={handleAddPhotos}
          onRemovePhoto={handleRemovePhoto}
        />

        <div className="stage">
          {viewing && (
            <div className="notice-bar">
              <span>
                {t('viewing.label', { number: viewing.number })}
                {viewing.prompt && <> · “{t.server(viewing.prompt)}”</>}
              </span>
              <button type="button" className="btn btn--primary" onClick={handleRestore}>
                {t('viewing.restore')}
              </button>
              <button type="button" className="btn" onClick={() => setViewing(null)}>
                {t('viewing.back')}
              </button>
            </div>
          )}
          {editing && (
            <div className="notice-bar">
              <span>{t('editing.hint')}</span>
              <button type="button" className="btn btn--primary" onClick={handleSaveEdit} disabled={savingEdit}>
                {savingEdit ? t('editing.saving') : t('editing.save')}
              </button>
              <button type="button" className="btn" onClick={stopEditing} disabled={savingEdit}>
                {t('editing.cancel')}
              </button>
            </div>
          )}

          {editing && (
            <EditToolbar
              selection={selection}
              languages={editLangs}
              projectId={projectId}
              send={(command) => preview.current?.sendCommand(command)}
              onUploaded={(photo) => setEditPhotos((all) => [...all, photo])}
            />
          )}
          <div className="preview-card card">
            <div className="preview-card__bar">
              <span>{t('preview.title')}</span>
              {publishedUrl && (
                <span className={`preview-card__badge${publishedStale ? ' preview-card__badge--stale' : ''}`}>
                  {publishedStale ? t('preview.unpublishedChanges') : t('preview.published')}
                </span>
              )}
              <div className="device" role="group" aria-label={t('preview.device')}>
                {(['desktop', 'phone'] as const).map((d) => (
                  <button
                    key={d}
                    type="button"
                    aria-pressed={device === d}
                    className={`device__option${device === d ? ' device__option--active' : ''}`}
                    onClick={() => setDevice(d)}
                  >
                    {d === 'desktop' ? t('preview.desktop') : t('preview.phone')}
                  </button>
                ))}
              </div>
            </div>
            <Preview
              ref={preview}
              html={viewing?.html ?? html}
              building={loading}
              liveCode={liveCode}
              editing={editing}
              onSelect={setSelection}
              onLanguages={setEditLangs}
              device={device}
            />
          </div>

          {html && !loading && !editing && projectId && (
            <SiteActions
              projectId={projectId}
              publishedUrl={publishedUrl}
              stale={publishedStale}
              busy={publishBusy}
              historyOpen={historyOpen}
              onToggleHistory={() => setHistoryOpen((open) => !open)}
              bilingual={/\sdata-l="/.test(html ?? '')}
              onAddLanguage={() => handleSend(t('lang.addPrompt'), true)}
              onEditText={() => {
                setViewing(null) // edits always apply to the current version
                setEditing(true)
              }}
              onDownload={handleDownload}
              onPublish={() => changePublished('POST')}
              onUnpublish={() => changePublished('DELETE')}
            />
          )}
          {html && !loading && !editing && projectId && <ReviewPanel projectId={projectId} />}
          {publishedUrl && !loading && telegram?.available && !telegram.connected && /<form[\s>]/i.test(html ?? '') && (
            <p className="telegram-hint">{t('telegram.hint')}</p>
          )}
          {historyOpen && projectId && !loading && !editing && (
            <VersionHistory
              projectId={projectId}
              refreshKey={historyVersion}
              viewingId={viewing?.id ?? null}
              onView={handleViewVersion}
            />
          )}
        </div>
      </main>

      {galleryOpen && (
        <Gallery
          currentId={projectId}
          onSelect={handleGallerySelect}
          onDelete={handleGalleryDelete}
          onRename={handleGalleryRename}
          onClose={() => setGalleryOpen(false)}
        />
      )}
    </Shell>
  )
}

// What's been streamed so far, if it's far enough along to be worth showing:
// once the <body> has started, browsers render a half-written page fine.
function partialPage(written: string): string | null {
  const text = written.replace(/^\s*```[a-zA-Z]*\n?/, '')
  return /<body[\s>]/i.test(text) ? text : null
}
