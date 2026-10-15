import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { Translate, useT } from '../i18n'

export type VersionSummary = { id: number; number: number; prompt: string; created_at: string }

type Props = {
  projectId: string
  refreshKey: number // bump to reload, e.g. after a generation or restore
  viewingId: number | null
  onView: (version: VersionSummary) => void
}

export default function VersionHistory({ projectId, refreshKey, viewingId, onView }: Props) {
  const t = useT()
  const [items, setItems] = useState<VersionSummary[] | null>(null)

  useEffect(() => {
    apiFetch(`/api/projects/${projectId}/versions`)
      .then((res) => (res.ok ? res.json() : { items: [] }))
      .then((data) => setItems(data.items))
      .catch(() => setItems([]))
  }, [projectId, refreshKey])

  if (items === null) return <p className="versions__empty">{t('history.loading')}</p>

  return (
    <ol className="versions card">
      {items.map((v, i) => (
        <li key={v.id}>
          <button
            type="button"
            className={`versions__item${viewingId === v.id ? ' versions__item--viewing' : ''}`}
            onClick={() => onView(v)}
          >
            <span className="versions__number">v{v.number}</span>
            <span className="versions__prompt">{v.prompt ? t.server(v.prompt) : t('history.first')}</span>
            <span className="versions__time">{i === 0 ? t('history.current') : timeAgo(v.created_at, t)}</span>
          </button>
        </li>
      ))}
    </ol>
  )
}

function timeAgo(iso: string, t: Translate): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (minutes < 1) return t('history.justNow')
  if (minutes < 60) return t('history.minutes', { n: minutes })
  const hours = Math.round(minutes / 60)
  if (hours < 24) return t('history.hours', { n: hours })
  return new Date(iso).toLocaleDateString(t.lang === 'uk' ? 'uk-UA' : 'en-GB')
}
