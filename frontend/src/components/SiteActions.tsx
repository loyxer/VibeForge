import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { useT } from '../i18n'
import QrDialog from './QrDialog'

type Visits = { today: number; views_7d: number; visitors_7d: number; total: number }

type Props = {
  projectId: string
  publishedUrl: string | null
  // The site was edited after it was published: the link shows an older version.
  stale: boolean
  busy: boolean
  historyOpen: boolean
  onToggleHistory: () => void
  // The site already has two languages.
  bilingual: boolean
  multipage: boolean
  onAddPages: () => void
  onLogo: () => void
  onAddLanguage: () => void
  onEditText: () => void
  onDownload: () => void
  onPublish: () => void
  onUnpublish: () => void
}

export default function SiteActions({
  projectId,
  publishedUrl,
  stale,
  busy,
  historyOpen,
  onToggleHistory,
  bilingual,
  onAddLanguage,
  multipage,
  onAddPages,
  onLogo,
  onEditText,
  onDownload,
  onPublish,
  onUnpublish,
}: Props) {
  const t = useT()
  const [copied, setCopied] = useState(false)
  const [qrOpen, setQrOpen] = useState(false)
  const [visits, setVisits] = useState<Visits | null>(null)
  // May search engines (Google) list the page? Off until the owner says so.
  const [indexable, setIndexable] = useState(false)

  useEffect(() => {
    setVisits(null)
    if (!publishedUrl) return
    apiFetch(`/api/projects/${projectId}/visits`)
      .then((res) => (res.ok ? res.json() : null))
      .then(setVisits)
      .catch(() => {})
    apiFetch(`/api/projects/${projectId}/seo`)
      .then((res) => (res.ok ? res.json() : null))
      .then((s) => setIndexable(Boolean(s?.indexable)))
      .catch(() => {})
  }, [projectId, publishedUrl])

  async function toggleIndexable(value: boolean) {
    setIndexable(value)
    const res = await apiFetch(`/api/projects/${projectId}/seo`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ indexable: value }),
    }).catch(() => null)
    if (!res?.ok) setIndexable(!value)
  }

  async function copy() {
    if (!publishedUrl) return
    await navigator.clipboard.writeText(publishedUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="site-actions">
      <div className="site-actions__row">
        <button type="button" className="btn" onClick={onEditText} title={t('actions.editTextHint')}>
          {t('actions.editText')}
        </button>
        <button type="button" className="btn" onClick={onToggleHistory} aria-expanded={historyOpen}>
          {historyOpen ? t('actions.hideHistory') : t('actions.history')}
        </button>
        {!bilingual && (
          <button type="button" className="btn" onClick={onAddLanguage} title={t('actions.addLanguageHint')}>
            {t('actions.addLanguage')}
          </button>
        )}
        {!multipage && (
          <button type="button" className="btn" onClick={onAddPages} title={t('actions.addPagesHint')}>
            {t('actions.addPages')}
          </button>
        )}
        <button type="button" className="btn" onClick={onLogo} title={t('logo.buttonHint')}>
          {t('logo.button')}
        </button>
        <button type="button" className="btn" onClick={onDownload}>
          {t('actions.download')}
        </button>
        <span className="site-actions__spacer" />
        {!publishedUrl && (
          <button type="button" className="btn btn--blue" onClick={onPublish} disabled={busy}>
            {busy ? t('actions.publishing') : t('actions.publish')}
          </button>
        )}
        {publishedUrl && stale && (
          <button type="button" className="btn btn--blue" onClick={onPublish} disabled={busy}>
            {busy ? t('actions.updating') : t('actions.update')}
          </button>
        )}
      </div>

      {publishedUrl && (
        <div className="site-actions__published">
          <span className="site-actions__label">{t('actions.liveAt')}</span>
          <a href={publishedUrl} target="_blank" rel="noopener noreferrer">
            {publishedUrl.replace(/^https?:\/\//, '')}
          </a>
          <button type="button" className="btn btn--small" onClick={copy}>
            {copied ? t('actions.copied') : t('actions.copy')}
          </button>
          <button type="button" className="btn btn--small" onClick={() => setQrOpen(true)}>
            {t('qr.button')}
          </button>
          <button type="button" className="btn btn--small" onClick={onUnpublish} disabled={busy}>
            {t('actions.unpublish')}
          </button>
          {visits && (
            <p className="site-actions__visits">
              {visits.total === 0
                ? t('visits.none')
                : t('visits.line', {
                    today: visits.today,
                    week: visits.views_7d,
                    people: visits.visitors_7d,
                    total: visits.total,
                  })}
            </p>
          )}
          <label className="site-actions__seo">
            <input type="checkbox" checked={indexable} onChange={(e) => toggleIndexable(e.target.checked)} />
            <span>
              {t('seo.label')}
              <small>{indexable ? t('seo.on') : t('seo.off')}</small>
            </span>
          </label>
          {stale && <p className="site-actions__stale">{t('actions.stale')}</p>}
        </div>
      )}
      {qrOpen && publishedUrl && <QrDialog url={publishedUrl} onClose={() => setQrOpen(false)} />}
    </div>
  )
}
