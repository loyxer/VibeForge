import { useState } from 'react'

type Props = {
  publishedUrl: string | null
  // The site was edited after it was published: the link shows an older version.
  stale: boolean
  busy: boolean
  historyOpen: boolean
  onToggleHistory: () => void
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
  onDownload,
  onPublish,
  onUnpublish,
}: Props) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    if (!publishedUrl) return
    await navigator.clipboard.writeText(publishedUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="site-actions">
      <div className="site-actions__row">
        <button type="button" onClick={onToggleHistory} aria-expanded={historyOpen}>
          {historyOpen ? 'Hide history' : 'History'}
        </button>
        <button type="button" onClick={onDownload}>
          Download HTML
        </button>
        {!publishedUrl && (
          <button type="button" className="site-actions__primary" onClick={onPublish} disabled={busy}>
            {busy ? 'Publishing…' : 'Publish'}
          </button>
        )}
      </div>

      {publishedUrl && (
        <div className="site-actions__published">
          <span className="site-actions__label">Live at</span>
          <a href={publishedUrl} target="_blank" rel="noopener noreferrer">
            {publishedUrl.replace(/^https?:\/\//, '')}
          </a>
          <button type="button" onClick={copy}>
            {copied ? 'Copied!' : 'Copy link'}
          </button>
          <button type="button" onClick={onUnpublish} disabled={busy}>
            Unpublish
          </button>
          {stale && (
            <div className="site-actions__stale">
              Your latest changes aren't live yet.
              <button type="button" className="site-actions__primary" onClick={onPublish} disabled={busy}>
                {busy ? 'Updating…' : 'Update published site'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
