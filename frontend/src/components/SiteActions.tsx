import { useState } from 'react'
import { useT } from '../i18n'
import QrDialog from './QrDialog'

type Props = {
  publishedUrl: string | null
  // The site was edited after it was published: the link shows an older version.
  stale: boolean
  busy: boolean
  historyOpen: boolean
  onToggleHistory: () => void
  onEditText: () => void
  onDownload: () => void
  onPublish: () => void
  onUnpublish: () => void
}

export default function SiteActions({
  publishedUrl,
  stale,
  busy,
  historyOpen,
  onToggleHistory,
  onEditText,
  onDownload,
  onPublish,
  onUnpublish,
}: Props) {
  const t = useT()
  const [copied, setCopied] = useState(false)
  const [qrOpen, setQrOpen] = useState(false)

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
          {stale && <p className="site-actions__stale">{t('actions.stale')}</p>}
        </div>
      )}
      {qrOpen && publishedUrl && <QrDialog url={publishedUrl} onClose={() => setQrOpen(false)} />}
    </div>
  )
}
