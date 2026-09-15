import { useState } from 'react'
import Chat, { ChatMessage } from './components/Chat'
import Preview from './components/Preview'

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [html, setHtml] = useState<string | null>(null)
  const [projectId, setProjectId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSend(prompt: string) {
    setMessages((m) => [...m, { role: 'user', text: prompt }])
    setLoading(true)

    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, project_id: projectId }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? `Server error: ${res.status}`)

      setHtml(data.html)
      setProjectId(data.project_id)
      setMessages((m) => [...m, { role: 'assistant', text: 'Done — updated the preview.' }])
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Generation failed'
      setMessages((m) => [...m, { role: 'assistant', text: `Error: ${message}` }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header>
        <h1>VibeForge</h1>
        <p>Describe a site in plain words — watch it build, live.</p>
      </header>

      <main>
        <Chat messages={messages} loading={loading} onSend={handleSend} />
        <div>
          <Preview html={html} />
          {projectId && (
            <a
              className="download-link"
              href={`/api/projects/${projectId}/download`}
              download
            >
              Download HTML
            </a>
          )}
        </div>
      </main>
    </div>
  )
}
