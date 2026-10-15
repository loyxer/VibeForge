import { useEffect, useRef, useState } from 'react'
import { apiFetch } from '../api'
import { useT } from '../i18n'

type GalleryItem = {
  id: string
  history: string[]
}

type ProjectData = {
  html: string
  history: string[]
  published_url: string | null
}

export type GallerySelection = {
  projectId: string
  html: string
  history: string[]
  publishedUrl: string | null
}

type Props = {
  currentId: string | null
  onSelect: (selection: GallerySelection) => void
  onDelete: (projectId: string) => void
  onClose: () => void
}

// "My sites": every project as a card with a live miniature of the page.
export default function Gallery({ currentId, onSelect, onDelete, onClose }: Props) {
  const t = useT()
  const [items, setItems] = useState<GalleryItem[] | null>(null)
  const closeButton = useRef<HTMLButtonElement>(null)
  // The parent passes a new function each render; keep the latest without
  // re-running the effect below (which would steal focus every time).
  const close = useRef(onClose)
  close.current = onClose

  useEffect(() => {
    apiFetch('/api/projects')
      .then((res) => (res.ok ? res.json() : { items: [] }))
      .then((data) => setItems(data.items ?? []))
      .catch(() => setItems([]))
  }, [])

  useEffect(() => {
    closeButton.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && close.current()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  async function handleDelete(item: GalleryItem) {
    const name = item.history[0] ?? item.id.slice(0, 8)
    if (!window.confirm(t('gallery.confirmDelete', { name: t.server(name) }))) return
    const res = await apiFetch(`/api/projects/${item.id}`, { method: 'DELETE' })
    if (!res.ok && res.status !== 404) return
    setItems((prev) => prev?.filter((p) => p.id !== item.id) ?? null)
    onDelete(item.id)
  }

  return (
    <div className="modal" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal__panel card" role="dialog" aria-modal="true" aria-labelledby="gallery-title">
        <div className="modal__head">
          <h2 id="gallery-title">{t('gallery.title')}</h2>
          <button ref={closeButton} type="button" className="btn btn--small" onClick={onClose}>
            {t('gallery.close')}
          </button>
        </div>
        {items === null ? (
          <p className="gallery__empty">{t('gallery.loading')}</p>
        ) : items.length === 0 ? (
          <p className="gallery__empty">{t('gallery.empty')}</p>
        ) : (
          <ul className="gallery">
            {items.map((item) => (
              <SiteCard
                key={item.id}
                item={item}
                current={item.id === currentId}
                onOpen={onSelect}
                onDelete={() => handleDelete(item)}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

type CardProps = {
  item: GalleryItem
  current: boolean
  onOpen: (selection: GallerySelection) => void
  onDelete: () => void
}

function SiteCard({ item, current, onOpen, onDelete }: CardProps) {
  const t = useT()
  const [project, setProject] = useState<ProjectData | null>(null)

  useEffect(() => {
    apiFetch(`/api/projects/${item.id}`)
      .then((res) => (res.ok ? res.json() : null))
      .then(setProject)
      .catch(() => setProject(null))
  }, [item.id])

  async function open() {
    let data = project
    if (!data) {
      const res = await apiFetch(`/api/projects/${item.id}`)
      if (!res.ok) return
      data = (await res.json()) as ProjectData
    }
    onOpen({
      projectId: item.id,
      html: data.html,
      history: data.history ?? [],
      publishedUrl: data.published_url ?? null,
    })
  }

  const name = item.history[0] ?? item.id.slice(0, 8)

  return (
    <li className={`site-card${current ? ' site-card--current' : ''}`}>
      <button type="button" className="site-card__open" onClick={open}>
        <Thumb html={project?.html ?? null} />
        <span className="site-card__name">{t.server(name)}</span>
        <span className="site-card__meta">
          {current ? t('gallery.current') : t.plural('gallery.steps', item.history.length)}
        </span>
      </button>
      <button type="button" className="site-card__delete btn btn--small" onClick={onDelete}>
        {t('gallery.delete')}
      </button>
    </li>
  )
}

// The page drawn at desktop width and shrunk to fit the card. Scripts stay
// off (empty sandbox): a miniature only needs to look like the site.
function Thumb({ html }: { html: string | null }) {
  const box = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(0.2)

  useEffect(() => {
    const el = box.current
    if (!el) return
    const observer = new ResizeObserver(([entry]) => setScale(entry.contentRect.width / 1280))
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return (
    <div className="thumb" ref={box}>
      {html && (
        <iframe
          srcDoc={html}
          sandbox=""
          loading="lazy"
          tabIndex={-1}
          aria-hidden="true"
          title=""
          style={{ transform: `scale(${scale})` }}
        />
      )}
    </div>
  )
}
