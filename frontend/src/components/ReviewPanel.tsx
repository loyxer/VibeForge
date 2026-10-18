import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { useT } from '../i18n'

type Comment = {
  id: number
  author: string
  text: string
  label: string
  resolved: boolean
  created_at: string
}

type State = { url: string | null; comments: Comment[] }

/** The owner's side of the client link: switch it on, read the comments, tick them off. */
export default function ReviewPanel({ projectId }: { projectId: string }) {
  const t = useT()
  const [state, setState] = useState<State | null>(null)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)

  const load = useCallback(async () => {
    const res = await apiFetch(`/api/projects/${projectId}/review`).catch(() => null)
    if (res?.ok) setState(await res.json())
  }, [projectId])

  useEffect(() => {
    setState(null)
    setOpen(false)
    load()
  }, [load])

  // Comments arrive while the owner works: look again every half minute.
  useEffect(() => {
    if (!state?.url) return
    const timer = setInterval(load, 30_000)
    return () => clearInterval(timer)
  }, [state?.url, load])

  async function change(path: string, method: string, body?: object) {
    setBusy(true)
    try {
      const res = await apiFetch(`/api/projects/${projectId}/review${path}`, {
        method,
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      })
      if (res.ok) setState(await res.json())
    } finally {
      setBusy(false)
    }
  }

  async function copy() {
    if (!state?.url) return
    await navigator.clipboard.writeText(state.url)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  if (!state) return null
  const openCount = state.comments.filter((c) => !c.resolved).length

  return (
    <div className="review-panel">
      <button
        type="button"
        className="btn review-panel__toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {openCount > 0 ? t('review.titleCount', { n: openCount }) : t('review.title')}
      </button>

      {open && (
        <div className="review-panel__body card">
          {!state.url ? (
            <>
              <p>{t('review.intro')}</p>
              <button type="button" className="btn btn--primary" disabled={busy} onClick={() => change('', 'POST')}>
                {t('review.start')}
              </button>
            </>
          ) : (
            <>
              <div className="review-panel__link">
                <span className="site-actions__label">{t('review.linkLabel')}</span>
                <a href={state.url} target="_blank" rel="noopener noreferrer">
                  {state.url}
                </a>
                <button type="button" className="btn btn--small" onClick={copy}>
                  {copied ? t('actions.copied') : t('actions.copy')}
                </button>
                <button type="button" className="btn btn--small" onClick={load}>
                  ↻
                </button>
                <button
                  type="button"
                  className="btn btn--small"
                  disabled={busy}
                  title={t('review.stopHint')}
                  onClick={() => change('', 'DELETE')}
                >
                  {t('review.stop')}
                </button>
              </div>
            </>
          )}

          {state.comments.length === 0 ? (
            state.url && <p className="review-panel__empty">{t('review.none')}</p>
          ) : (
            <ol className="review__list">
              {state.comments.map((c, i) => (
                <li key={c.id} className={c.resolved ? 'review__item review__item--done' : 'review__item'}>
                  <span className="review__number review__number--static">{i + 1}</span>
                  <div>
                    <strong>{c.author || t('review.client')}</strong>
                    {c.label && <span className="review__target"> · {c.label}</span>}
                    <p>{c.text}</p>
                    <div className="review__buttons">
                      <button
                        type="button"
                        className="btn btn--small"
                        disabled={busy}
                        onClick={() => change(`/comments/${c.id}`, 'PATCH', { resolved: !c.resolved })}
                      >
                        {c.resolved ? t('review.reopen') : t('review.resolve')}
                      </button>
                      <button
                        type="button"
                        className="btn btn--small btn--link"
                        disabled={busy}
                        onClick={() => change(`/comments/${c.id}`, 'DELETE')}
                      >
                        {t('review.delete')}
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  )
}
