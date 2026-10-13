import { useEffect, useState } from 'react'
import { apiFetch } from '../api'

export type VersionSummary = { id: number; number: number; prompt: string; created_at: string }

type Props = {
  projectId: string
  refreshKey: number // bump to reload, e.g. after a generation or restore
  viewingId: number | null
  onView: (version: VersionSummary) => void
}

export default function VersionHistory({ projectId, refreshKey, viewingId, onView }: Props) {
  const [items, setItems] = useState<VersionSummary[] | null>(null)

  useEffect(() => {
    apiFetch(`/api/projects/${projectId}/versions`)
      .then((res) => (res.ok ? res.json() : { items: [] }))
      .then((data) => setItems(data.items))
      .catch(() => setItems([]))
  }, [projectId, refreshKey])

  if (items === null) return <p className="versions__empty">Loading history…</p>

  return (
    <ol className="versions">
      {items.map((v, i) => (
        <li key={v.id}>
          <button
            type="button"
            className={`versions__item${viewingId === v.id ? ' versions__item--viewing' : ''}`}
            onClick={() => onView(v)}
          >
            <span className="versions__number">v{v.number}</span>
            <span className="versions__prompt">{v.prompt || 'First version'}</span>
            <span className="versions__time">{i === 0 ? 'current' : timeAgo(v.created_at)}</span>
          </button>
        </li>
      ))}
    </ol>
  )
}

function timeAgo(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  return new Date(iso).toLocaleDateString()
}
