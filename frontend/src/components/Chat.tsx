import { FormEvent, useEffect, useRef, useState } from 'react'
import type { Usage } from '../api'
import { isKey, Key, useT } from '../i18n'
import Mascot from './Mascot'
import StylePicker from './StylePicker'

type Params = Record<string, string | number>

// What the person typed, a reply of ours, or an error — either a key of
// ours or the server's English text. Kept untranslated so switching the
// language re-translates the whole conversation.
export type ChatMessage =
  | { role: 'user'; text: string }
  | { role: 'assistant'; key: Key }
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
}: Props) {
  const t = useT()
  const [input, setInput] = useState('')
  const limitReached = usage?.remaining_today === 0
  const list = useRef<HTMLDivElement>(null)

  // Keep the newest message (and the live progress line) in view — by
  // scrolling the message list only, never the whole page.
  useEffect(() => {
    if (list.current) list.current.scrollTop = list.current.scrollHeight
  }, [messages, loading, progress])

  const say = (text: string, params?: Params) => (isKey(text) ? t(text, params) : t.server(text))

  function submitPrompt() {
    const prompt = input.trim()
    if (!prompt || loading || limitReached || paused) return
    onSend(prompt)
    setInput('')
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    submitPrompt()
  }

  return (
    <section className="chat card">
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
        {messages.map((m, i) =>
          m.role === 'user' ? (
            <div key={i} className="bubble bubble--user">
              {t.server(m.text)}
            </div>
          ) : (
            <div key={i} className="reply">
              <Mascot />
              {'key' in m ? (
                <div className="bubble bubble--assistant">{t(m.key)}</div>
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
          id="prompt"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={isNewSite ? t('chat.placeholderNew') : t('chat.placeholderEdit')}
          rows={3}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submitPrompt()
            }
          }}
        />
        <button
          type="submit"
          className="btn btn--orange btn--big"
          disabled={loading || limitReached || paused || !input.trim()}
        >
          {loading ? t('chat.sending') : isNewSite ? t('chat.send') : t('chat.sendEdit')}
        </button>
      </form>
    </section>
  )
}
