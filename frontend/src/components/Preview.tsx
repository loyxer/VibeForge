import { useEffect, useRef, useState } from 'react'

type Props = {
  html: string | null
  building: boolean
  // The tail of the code being written right now, shown as a live strip.
  liveCode: string
}

// Double-buffered: a new version loads in a hidden frame and is swapped in
// only once it has finished loading (fonts, images and all). Reloading the
// visible frame instead would flash white on every update while the site
// streams in.
export default function Preview({ html, building, liveCode }: Props) {
  const [slots, setSlots] = useState<[string | null, string | null]>([null, null])
  const [active, setActive] = useState(0)
  const loading = useRef(false)
  const latest = useRef<string | null>(null)

  function loadInto(slot: number, next: string) {
    loading.current = true
    setSlots((s) => {
      const copy: [string | null, string | null] = [s[0], s[1]]
      copy[slot] = next
      return copy
    })
  }

  useEffect(() => {
    latest.current = html
    if (html === null) {
      setSlots([null, null])
      loading.current = false
    } else if (!loading.current && html !== slots[active]) {
      loadInto(1 - active, html)
    }
    // Only reacts to new HTML; the slots are managed by handleLoad.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [html])

  function handleLoad(slot: number) {
    if (slot === active || slots[slot] === null) return
    setActive(slot)
    loading.current = false
    // A newer version arrived while this one was loading — load it next.
    if (latest.current !== null && latest.current !== slots[slot]) {
      loadInto(1 - slot, latest.current)
    }
  }

  const shown = slots[active]

  return (
    <div className="preview">
      {[0, 1].map((slot) =>
        slots[slot] !== null ? (
          <iframe
            key={slot}
            className={`preview__frame${slot === active ? '' : ' preview__frame--hidden'}`}
            srcDoc={slots[slot]!}
            sandbox="allow-scripts allow-forms allow-popups"
            title={slot === active ? 'Live preview' : 'Next version (loading)'}
            onLoad={() => handleLoad(slot)}
          />
        ) : null,
      )}
      {!shown && (
        <div className="preview__placeholder">
          {building ? 'Your site will appear here as it is written…' : 'Your site will appear here'}
        </div>
      )}
      {building && shown && <div className="preview__badge">Building…</div>}
      {building && liveCode && (
        <pre className="preview__code">{liveCode.split('\n').slice(-7).join('\n')}</pre>
      )}
    </div>
  )
}
