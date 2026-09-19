import { useState } from 'react'
import Chat, { ChatMessage } from './components/Chat'
import Preview from './components/Preview'
import Gallery, { GallerySelection } from './components/Gallery'
import { apiUrl } from './api'

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [html, setHtml] = useState<string | null>(null)
  const [projectId, setProjectId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [galleryVersion, setGalleryVersion] = useState(0)

  async function handleSend(prompt: string) {
    setMessages((m) => [...m, { role: 'user', text: prompt }])
    setLoading(true)

    try {
      const post = (id: string | null) =>
        fetch(apiUrl('/api/generate'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt, project_id: id }),
        })

      let res = await post(projectId)
      let data = await res.json()

      if (res.status === 404 && projectId) {
        // The backend lost this project (e.g. a free-tier restart wiped its
        // storage) but we still remember its id — start a fresh one instead
        // of failing on an edit the server can no longer make sense of.
        res = await post(null)
        data = await res.json()
      }

      if (!res.ok) throw new Error(data.detail ?? `Server error: ${res.status}`)

      setHtml(data.html)
      setProjectId(data.project_id)
      setMessages((m) => [...m, { role: 'assistant', text: 'Done — updated the preview.' }])
      setGalleryVersion((v) => v + 1)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Generation failed'
      setMessages((m) => [...m, { role: 'assistant', text: `Error: ${message}` }])
    } finally {
      setLoading(false)
    }
  }

  function handleGallerySelect(selection: GallerySelection) {
    setProjectId(selection.projectId)
    setHtml(selection.html)
    setMessages(
      selection.history.flatMap((prompt) => [
        { role: 'user' as const, text: prompt },
        { role: 'assistant' as const, text: 'Done — updated the preview.' },
      ]),
    )
  }

  function handleGalleryDelete(deletedId: string) {
    if (deletedId === projectId) {
      setProjectId(null)
      setHtml(null)
      setMessages([])
    }
  }

  return (
    <div className="app">
      <header>
        <h1>VibeForge</h1>
        <p>Describe a site in plain words — watch it build, live.</p>
      </header>

      <main>
        <div className="sidebar">
          <Chat messages={messages} loading={loading} onSend={handleSend} />
          <Gallery
            refreshKey={galleryVersion}
            onSelect={handleGallerySelect}
            onDelete={handleGalleryDelete}
          />
        </div>
        <div>
          <Preview html={html} />
          {projectId && (
            <a
              className="download-link"
              href={apiUrl(`/api/projects/${projectId}/download`)}
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
