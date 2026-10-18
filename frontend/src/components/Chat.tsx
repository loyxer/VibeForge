import { FormEvent, useEffect, useRef, useState } from 'react'
import type { Usage } from '../api'
import { isKey, Key, useT } from '../i18n'
import Mascot from './Mascot'
import { MAX_PHOTOS_PER_SITE, TrayPhoto } from '../photoUpload'
import StylePicker from './StylePicker'

type Params = Record<string, string | number>

// Ready-made requests for someone who doesn't know what to write yet.
const EXAMPLES: { label: Key; prompt: Key }[] = [
  { label: 'examples.cafe', prompt: 'examples.cafePrompt' },
  { label: 'examples.photographer', prompt: 'examples.photographerPrompt' },
  { label: 'examples.guesthouse', prompt: 'examples.guesthousePrompt' },
  { label: 'examples.salon', prompt: 'examples.salonPrompt' },
  { label: 'examples.trainer', prompt: 'examples.trainerPrompt' },
]

// What the person typed, a reply of ours, or an error — either a key of
// ours or the server's English text. Kept untranslated so switching the
// language re-translates the whole conversation.
export type ChatMessage =
  | { role: 'user'; text: string; photos?: number }
  | { role: 'assistant'; key: Key; params?: Params }
  | { role: 'assistant'; error: string }

// The live line while a site is being built: a key of ours or server text.
export type Progress = { text: string; params?: Params }

type Props = {
  // The site being worked on, or "New site".
  title: string
  messages: ChatMessage[]
  loading: boolean
  progress: Progress | null
  usage: Usage | null
  // Picking a style only makes sense before the first generation of a site.
  isNewSite: boolean
  // While the text is being edited by hand, sending is paused.
  paused: boolean
  style: string | null
  onStyleChange: (style: string | null) => void
  onNewSite: () => void
  onSend: (prompt: string) => void
  // The person's own photos to send with the next message.
  tray: TrayPhoto[]
  onAddPhotos: (files: File[]) => void
  onRemovePhoto: (key: string) => void
}

export default function Chat({
  title,
  messages,
  loading,
  progress,
  usage,
  isNewSite,
  paused,
  style,
  onStyleChange,
  onNewSite,
  onSend,
  tray,
  onAddPhotos,
  onRemovePhoto,
}: Props) {
  const t = useT()
  const [input, setInput] = useState('')
  const limitReached = usage?.remaining_today === 0
  const uploading = tray.some((p) => p.status === 'uploading')
  const photoErrors = tray.flatMap((p) => (p.error ? [p.error] : []))
  const list = useRef<HTMLDivElement>(null)
  const canAddPhotos = tray.length < MAX_PHOTOS_PER_SITE && !loading
  // Dragging files over the chat: enter/leave also fire for every child
  // element, so count them instead of toggling on each event.
  const [dragging, setDragging] = useState(false)
  const dragDepth = useRef(0)
  const box = useRef<HTMLTextAreaElement>(null)

  // Keep the newest message (and the live progress line) in view — by
  // scrolling the message list only, never the whole page.
  useEffect(() => {
    // An empty chat starts at the top, where the greeting is.
    if (list.current && messages.length) list.current.scrollTop = list.current.scrollHeight
  }, [messages, loading, progress])

  const say = (text: string, params?: Params) => (isKey(text) ? t(text, params) : t.server(text))

  function submitPrompt() {
    const prompt = input.trim()
    if (!prompt || loading || limitReached || paused || uploading) return
    onSend(prompt)
    setInput('')
  }

  const hasFiles = (e: React.DragEvent) => Array.from(e.dataTransfer.types).includes('Files')

  const dragHandlers = {
    onDragEnter(e: React.DragEvent) {
      if (!hasFiles(e)) return
      e.preventDefault()
      dragDepth.current += 1
      setDragging(true)
    },
    onDragOver(e: React.DragEvent) {
      if (hasFiles(e)) e.preventDefault() // required, or the browser opens the file instead
    },
    onDragLeave(e: React.DragEvent) {
      if (!hasFiles(e)) return
      dragDepth.current = Math.max(0, dragDepth.current - 1)
      if (dragDepth.current === 0) setDragging(false)
    },
    onDrop(e: React.DragEvent) {
      if (!hasFiles(e)) return
      e.preventDefault()
      dragDepth.current = 0
      setDragging(false)
      const images = Array.from(e.dataTransfer.files).filter((f) => f.type.startsWith('image/'))
      if (canAddPhotos && images.length) onAddPhotos(images)
    },
  }

  function handlePaste(e: React.ClipboardEvent) {
    const images = Array.from(e.clipboardData.files).filter((f) => f.type.startsWith('image/'))
    if (!images.length) return // plain text pastes as usual
    e.preventDefault()
    if (canAddPhotos) onAddPhotos(images)
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    submitPrompt()
  }

  return (
    <section className={`chat card${dragging ? ' chat--dragging' : ''}`} {...dragHandlers}>
      {dragging && <div className="chat__drop">{t('photos.drop')}</div>}
      <div className="chat__head">
        <h2 className="chat__title" title={title}>
          {title}
        </h2>
        {!isNewSite && (
          <button type="button" className="btn btn--small btn--link" onClick={onNewSite} disabled={loading}>
            {t('chat.newSiteButton')}
          </button>
        )}
      </div>

      <div className="chat__messages" ref={list}>
        {messages.length === 0 && (
          <div className="reply">
            <Mascot />
            <div className="bubble bubble--assistant">{t('chat.empty')}</div>
          </div>
        )}
        {messages.length === 0 && isNewSite && (
          <div className="examples">
            <div className="chips" role="group" aria-label={t('examples.title')}>
              {EXAMPLES.map((e) => (
                <button
                  key={e.label}
                  type="button"
                  className="chip"
                  onClick={() => {
                    // Filled in, not sent: the person can adjust it first.
                    setInput(t(e.prompt))
                    box.current?.focus()
                  }}
                >
                  {t(e.label)}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) =>
          m.role === 'user' ? (
            <div key={i} className="bubble bubble--user">
              {t.server(m.text)}
              {m.photos ? <span className="bubble__photos">📎 {t.plural('photos.count', m.photos)}</span> : null}
            </div>
          ) : (
            <div key={i} className="reply">
              <Mascot />
              {'key' in m ? (
                <div className="bubble bubble--assistant">{t(m.key, m.params)}</div>
              ) : (
                <div className="bubble bubble--error">{t('reply.error', { detail: say(m.error) })}</div>
              )}
            </div>
          ),
        )}
        {loading && (
          <div className="reply reply--progress" aria-live="polite">
            <Mascot />
            <span>{progress ? say(progress.text, progress.params) : t('progress.generating')}</span>
            <span className="dots" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
          </div>
        )}
      </div>

      <form className="chat__form" onSubmit={handleSubmit}>
        {isNewSite && (
          <>
            <span className="chat__label">{t('chat.style')}</span>
            <StylePicker value={style} onChange={onStyleChange} />
          </>
        )}
        {limitReached && usage?.limit != null && (
          <p className="chat__limit">{t('usage.limitReached', { limit: usage.limit })}</p>
        )}
        <label className="chat__label" htmlFor="prompt">
          {isNewSite ? t('chat.labelNew') : t('chat.labelEdit')}
        </label>
        <textarea
          ref={box}
          id="prompt"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onPaste={handlePaste}
          placeholder={isNewSite ? t('chat.placeholderNew') : t('chat.placeholderEdit')}
          rows={3}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submitPrompt()
            }
          }}
        />
        {tray.length > 0 && (
          <ul className="photo-tray">
            {tray.map((p) => (
              <li key={p.key} className={`photo-tray__item photo-tray__item--${p.status}`}>
                <img src={p.preview} alt="" />
                {p.status === 'uploading' && <span className="photo-tray__spinner" aria-label={t('photos.uploading')} />}
                <button
                  type="button"
                  className="photo-tray__remove"
                  aria-label={t('photos.remove')}
                  onClick={() => onRemovePhoto(p.key)}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
        {photoErrors.length > 0 && <p className="chat__photo-error">{say(photoErrors[0])}</p>}
        <div className="chat__photos-row">
          <label className={`btn btn--small photo-add${canAddPhotos ? '' : ' photo-add--disabled'}`}>
            📎 {t('photos.add')}
            <input
              type="file"
              accept="image/*"
              multiple
              hidden
              disabled={!canAddPhotos}
              onChange={(e) => {
                onAddPhotos(Array.from(e.target.files ?? []))
                e.target.value = '' // picking the same file again still fires
              }}
            />
          </label>
          <span className="chat__photos-hint">
            {tray.length > 0
              ? t('photos.counter', { n: tray.length, max: MAX_PHOTOS_PER_SITE })
              : t('photos.hint', { max: MAX_PHOTOS_PER_SITE })}
          </span>
        </div>
        <button
          type="submit"
          className="btn btn--orange btn--big"
          disabled={loading || limitReached || paused || uploading || !input.trim()}
        >
          {loading ? t('chat.sending') : isNewSite ? t('chat.send') : t('chat.sendEdit')}
        </button>
      </form>
    </section>
  )
}
