import { FormEvent, useState } from 'react'
import type { Usage } from '../api'

export type ChatMessage = {
  role: 'user' | 'assistant'
  text: string
}

type Props = {
  messages: ChatMessage[]
  loading: boolean
  usage: Usage | null
  onSend: (prompt: string) => void
}

export default function Chat({ messages, loading, usage, onSend }: Props) {
  const [input, setInput] = useState('')
  const limitReached = usage?.remaining_today === 0

  function submitPrompt() {
    const prompt = input.trim()
    if (!prompt || loading || limitReached) return
    onSend(prompt)
    setInput('')
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    submitPrompt()
  }

  return (
    <div className="chat">
      <div className="chat__messages">
        {messages.length === 0 && (
          <p className="chat__empty">
            Describe the site you want, e.g. "a landing page for a coffee
            shop with a menu section".
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat__message chat__message--${m.role}`}>
            {m.text}
          </div>
        ))}
        {loading && <div className="chat__message chat__message--assistant">Generating…</div>}
      </div>

      <form className="chat__form" onSubmit={handleSubmit}>
        {usage?.limit != null && (
          <p className={`chat__usage${limitReached ? ' chat__usage--empty' : ''}`}>
            {limitReached
              ? `You've used all ${usage.limit} free generations for today — more tomorrow.`
              : `${usage.remaining_today} of ${usage.limit} generations left today`}
          </p>
        )}
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            messages.length === 0
              ? 'a landing page for a coffee shop'
              : 'make the button blue'
          }
          rows={3}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submitPrompt()
            }
          }}
        />
        <button type="submit" disabled={loading || limitReached || !input.trim()}>
          {loading ? 'Generating…' : 'Send'}
        </button>
      </form>
    </div>
  )
}
