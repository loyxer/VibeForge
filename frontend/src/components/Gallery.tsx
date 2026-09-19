import { useEffect, useState } from 'react'

type GalleryItem = {
  id: string
  history: string[]
}

export type GallerySelection = {
  projectId: string
  html: string
  history: string[]
}

type Props = {
  refreshKey: number
  onSelect: (selection: GallerySelection) => void
}

export default function Gallery({ refreshKey, onSelect }: Props) {
  const [items, setItems] = useState<GalleryItem[]>([])

  useEffect(() => {
    fetch('/api/projects')
      .then((res) => res.json())
      .then((data) => setItems(data.items ?? []))
      .catch(() => setItems([]))
  }, [refreshKey])

  async function handleClick(id: string) {
    const res = await fetch(`/api/projects/${id}`)
    if (!res.ok) return
    const data = await res.json()
    onSelect({ projectId: id, html: data.html, history: data.history ?? [] })
  }

  if (items.length === 0) {
    return <p className="gallery__empty">Your projects will show up here.</p>
  }

  return (
    <div className="gallery">
      <h2 className="gallery__title">Projects</h2>
      <div className="gallery__list">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className="gallery__item"
            onClick={() => handleClick(item.id)}
          >
            <span className="gallery__label">
              {item.history[0] ?? item.id.slice(0, 8)}
            </span>
            <span className="gallery__count">
              {item.history.length} step{item.history.length === 1 ? '' : 's'}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
