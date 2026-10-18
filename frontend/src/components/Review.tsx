import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { apiFetch } from '../api'
import { useT } from '../i18n'
import { ReviewMark, withReviewHelper } from '../reviewFrame'

type Comment = {
  id: number
  author: string
  text: string
  selector: string
  label: string
  resolved: boolean
  created_at: string
}

type Page = { name: string; html: string; comments: Comment[] }

const NAME_KEY = 'vibeforge.reviewName'

function savedName(): string {
  try {
    return localStorage.getItem(NAME_KEY) ?? ''
  } catch {
    return ''
  }
}

/** What a client sees at /r/<token>: the site, and a place to say what to change. */
export default function Review({ token }: { token: string }) {
  const t = useT()
  const frame = useRef<HTMLIFrameElement>(null)
  const [page, setPage] = useState<Page | null>(null)
  const [missing, setMissing] = useState(false)
  const [comments, setComments] = useState<Comment[]>([])
  const [commentMode, setCommentMode] = useState(true)
  const [picked, setPicked] = useState<{ selector: string; label: string } | null>(null)
  const [text, setText] = useState('')
  const [author, setAuthor] = useState(savedName)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch(`/api/reviews/${encodeURIComponent(token)}`)
      .then(async (res) => {
        if (!res.ok) return setMissing(true)
        const data: Page = await res.json()
        setPage(data)
        setComments(data.comments)
        document.title = t('rv.title', { name: data.name })
      })
      .catch(() => setMissing(true))
    // Loaded once per link; the page keeps its own state after that.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  // The page is built once, so adding a comment never reloads the site.
  const srcDoc = useMemo(() => (page ? withReviewHelper(page.html) : ''), [page])

  const marks: ReviewMark[] = comments
    .map((c, i) => ({ id: c.id, n: i + 1, selector: c.selector, resolved: c.resolved }))
    .filter((m) => m.selector)

  function post(message: object) {
    frame.current?.contentWindow?.postMessage(message, '*')
  }

  // What the helper inside the page tells us.
  useEffect(() => {
    function onMessage(event: MessageEvent) {
      if (event.source !== frame.current?.contentWindow) return
      const d = event.data
      if (d?.type === 'vf-ready') {
        post({ type: 'vf-mode', on: commentMode })
        post({ type: 'vf-marks', marks })
      } else if (d?.type === 'vf-pick') {
        setPicked({ selector: String(d.selector), label: String(d.label) })
        setError(null)
      } else if (d?.type === 'vf-badge') {
        document.getElementById(`comment-${d.id}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
      }
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  })

  useEffect(() => {
    post({ type: 'vf-mode', on: commentMode })
    if (!commentMode) setPicked(null)
  }, [commentMode])

  useEffect(() => {
    post({ type: 'vf-marks', marks })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [comments])

  function cancel() {
    setPicked(null)
    setText('')
    post({ type: 'vf-unpick' })
  }

  async function send(e: FormEvent) {
    e.preventDefault()
    if (!picked || !text.trim() || sending) return
    setSending(true)
    setError(null)
    try {
      try {
        localStorage.setItem(NAME_KEY, author)
      } catch {
        // Not remembered; fine.
      }
      const res = await apiFetch(`/api/reviews/${encodeURIComponent(token)}/comments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ author, text, selector: picked.selector, label: picked.label }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.detail ?? t('error.server', { status: res.status }))
      setComments((all) => [...all, data])
      cancel()
    } catch (err) {
      setError(err instanceof Error ? t.server(err.message) : t('error.generic'))
    } finally {
      setSending(false)
    }
  }

  if (missing) return <p className="review__missing card">{t('rv.notFound')}</p>
  if (!page) return <p className="review__missing">{t('rv.loading')}</p>

  return (
    <div className="review">
      <div className="review__site card">
        <iframe
          ref={frame}
          className="review__frame"
          srcDoc={srcDoc}
          sandbox="allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox"
          title={page.name}
        />
      </div>

      <aside className="review__panel card">
        <h2>{t('rv.title', { name: page.name })}</h2>
        <p className="review__intro">{t('rv.intro')}</p>

        <button
          type="button"
          className={`chip chip--wide${commentMode ? ' chip--active' : ''}`}
          aria-pressed={commentMode}
          onClick={() => setCommentMode((on) => !on)}
        >
          {commentMode ? t('rv.modeOn') : t('rv.modeOff')}
        </button>

        {picked && (
          <form className="review__form" onSubmit={send}>
            <p className="review__about">{t('rv.about', { label: picked.label })}</p>
            <input
              type="text"
              value={author}
              maxLength={60}
              placeholder={t('rv.name')}
              onChange={(e) => setAuthor(e.target.value)}
            />
            <textarea
              autoFocus
              rows={3}
              maxLength={1000}
              value={text}
              placeholder={t('rv.placeholder')}
              onChange={(e) => setText(e.target.value)}
            />
            {error && <p className="review__error">{error}</p>}
            <div className="review__buttons">
              <button type="submit" className="btn btn--primary" disabled={sending || !text.trim()}>
                {sending ? t('rv.sending') : t('rv.send')}
              </button>
              <button type="button" className="btn" onClick={cancel}>
                {t('editing.cancel')}
              </button>
            </div>
          </form>
        )}

        <h3>{t('rv.list')}</h3>
        {comments.length === 0 ? (
          <p className="review__empty">{t('rv.empty')}</p>
        ) : (
          <ol className="review__list">
            {comments.map((c, i) => (
              <li
                key={c.id}
                id={`comment-${c.id}`}
                className={c.resolved ? 'review__item review__item--done' : 'review__item'}
              >
                <button
                  type="button"
                  className="review__number"
                  onClick={() => post({ type: 'vf-focus', selector: c.selector })}
                  aria-label={t('rv.show')}
                >
                  {i + 1}
                </button>
                <div>
                  <strong>{c.author || t('review.client')}</strong>
                  {c.label && <span className="review__target"> · {c.label}</span>}
                  {c.resolved && <span className="review__badge"> ✓ {t('rv.done')}</span>}
                  <p>{c.text}</p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </aside>
    </div>
  )
}
