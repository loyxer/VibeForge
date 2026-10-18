import { useEffect, useRef, useState } from 'react'
import { isKey, useT } from '../i18n'
import { shrink, uploadPhoto } from '../photoUpload'
import type { EditorCommand, Selection, SiteLanguages } from '../textEditor'

type Props = {
  selection: Selection | null
  languages: SiteLanguages | null
  projectId: string | null
  send: (command: EditorCommand) => void
  // A photo the person just uploaded to put on the page.
  onUploaded: (photo: { id: string; url: string }) => void
}

// Links that run code instead of going somewhere are never accepted.
const UNSAFE_LINK = /^\s*(javascript|data|vbscript):/i

/** Tools for the element just clicked in the preview: colors, photo, link. */
export default function EditToolbar({ selection, languages, projectId, send, onUploaded }: Props) {
  const t = useT()
  const fileInput = useRef<HTMLInputElement>(null)
  const [href, setHref] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const linkOfSelection = selection?.href ?? null
  useEffect(() => {
    setHref(linkOfSelection ?? '')
    setError(null)
  }, [linkOfSelection, selection?.label])

  async function handleFile(file: File | undefined) {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const photo = await uploadPhoto(await shrink(file), projectId)
      onUploaded(photo)
      send({ cmd: 'photo', value: photo.url })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'error.generic'
      setError(isKey(message) ? t(message) : t.server(message))
    } finally {
      setBusy(false)
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  function applyLink() {
    if (UNSAFE_LINK.test(href)) return setError(t('edit.linkBad'))
    send({ cmd: 'href', value: href.trim() })
  }

  const languageSwitch = languages && (
    <span className="edit-tools__langs" role="group" aria-label={t('edit.siteLanguage')}>
      {t('edit.siteLanguage')}
      {languages.all.map((code) => (
        <button
          key={code}
          type="button"
          className={`btn btn--small${languages.current === code ? ' btn--active' : ''}`}
          aria-pressed={languages.current === code}
          onClick={() => send({ cmd: 'lang', value: code })}
        >
          {code === 'uk' ? 'УКР' : code === 'en' ? 'ENG' : code.toUpperCase()}
        </button>
      ))}
    </span>
  )

  if (!selection)
    return (
      <div className="edit-tools edit-tools--empty">
        <span>{t('edit.pick')}</span>
        {languageSwitch}
      </div>
    )

  return (
    <div className="edit-tools">
      {languageSwitch}
      <span className="edit-tools__what" title={selection.label}>
        {t('edit.selected', { label: selection.label })}
      </span>
      <label className="edit-tools__color">
        {t('edit.textColor')}
        <input type="color" value={selection.color} onChange={(e) => send({ cmd: 'color', value: e.target.value })} />
      </label>
      <label className="edit-tools__color">
        {t('edit.background')}
        <input type="color" value={selection.bg ?? '#ffffff'} onChange={(e) => send({ cmd: 'bg', value: e.target.value })} />
      </label>
      {selection.photo && (
        <>
          <button type="button" className="btn btn--small" disabled={busy} onClick={() => fileInput.current?.click()}>
            {busy ? t('edit.uploading') : t('edit.replacePhoto')}
          </button>
          <input
            ref={fileInput}
            type="file"
            accept="image/*"
            hidden
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
        </>
      )}
      {selection.href !== null && (
        <form
          className="edit-tools__link"
          onSubmit={(e) => {
            e.preventDefault()
            applyLink()
          }}
        >
          <input
            type="text"
            value={href}
            placeholder="https://…"
            aria-label={t('edit.link')}
            onChange={(e) => setHref(e.target.value)}
          />
          <button type="submit" className="btn btn--small">
            {t('edit.setLink')}
          </button>
        </form>
      )}
      <button type="button" className="btn btn--small" disabled={!selection.canUp} onClick={() => send({ cmd: 'up' })} title={t('edit.widerHint')}>
        {t('edit.wider')}
      </button>
      <button type="button" className="btn btn--small" disabled={!selection.canUndo} onClick={() => send({ cmd: 'undo' })}>
        {t('edit.undo')}
      </button>
      {error && <span className="edit-tools__error">{error}</span>}
    </div>
  )
}
