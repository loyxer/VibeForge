import { FormEvent, useState } from 'react'

export type ChatMessage = {
  role: 'user' | 'assistant'
  text: string
}

type Props = {
  messages: ChatMessage[]
  loading: boolean
  onSend: (prompt: string) => void
}

export default function Chat({ messages, loading, onSend }: Props) {
  const [input, setInput] = useState('')

  function submitPrompt() {
    const prompt = input.trim()
    if (!prompt || loading) return
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
        <button type="submit" disabled={loading || !input.trim()}>
          {loading ? 'Generating…' : 'Send'}
        </button>
      </form>
    </div>
  )
}
