import { FormEvent, useState } from 'react'
import { apiFetch } from '../api'
import { isKey, useT } from '../i18n'
import { Dialog } from './AccountDialogs'

type Props = {
  defaultName: string
  // Put the chosen logo on the site; throws if that fails.
  onApply: (svg: string) => Promise<void>
  onClose: () => void
}

const dataUri = (svg: string) => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`

// Three AI-drawn logos for the business, to pick from and put in the site's
// header, or to download as SVG. The AI part runs on the server; here we
// only ever show the logos as images, so nothing in them can run.
export default function LogoDialog({ defaultName, onApply, onClose }: Props) {
  const t = useT()
  const [name, setName] = useState(defaultName)
  const [brief, setBrief] = useState('')
  const [dark, setDark] = useState(false)
  const [logos, setLogos] = useState<string[]>([])
  const [shownDark, setShownDark] = useState(false)
  const [busy, setBusy] = useState(false)
  const [applying, setApplying] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function draw(e?: FormEvent) {
    e?.preventDefault()
    if (name.trim().length < 2) return setError(t('logo.needName'))
    setError(null)
    setBusy(true)
    try {
      const res = await apiFetch('/api/logos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, brief, dark }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.detail ?? t('error.server', { status: res.status }))
      setLogos(data.logos)
      setShownDark(dark)
    } catch (err) {
      const text = err instanceof Error ? err.message : ''
      setError(isKey(text) ? t(text) : text ? t.server(text) : t('error.generic'))
    } finally {
      setBusy(false)
    }
  }

  async function apply(index: number) {
    setApplying(index)
    setError(null)
    try {
      await onApply(logos[index])
    } catch (err) {
      setError(err instanceof Error ? err.message : t('error.generic'))
      setApplying(null)
    }
  }

  return (
    <Dialog title={t('logo.title')} onClose={onClose}>
      <form className="dialog__form" onSubmit={draw}>
        <input
          autoFocus
          maxLength={40}
          placeholder={t('logo.name')}
          aria-label={t('logo.name')}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <textarea
          rows={2}
          maxLength={300}
          placeholder={t('logo.brief')}
          aria-label={t('logo.brief')}
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
        />
        <span className="chat__label">{t('logo.header')}</span>
        <div className="dialog__kinds" role="group" aria-label={t('logo.header')}>
          <button type="button" className={`chip${dark ? '' : ' chip--active'}`} aria-pressed={!dark} onClick={() => setDark(false)}>
            {t('logo.light')}
          </button>
          <button type="button" className={`chip${dark ? ' chip--active' : ''}`} aria-pressed={dark} onClick={() => setDark(true)}>
            {t('logo.dark')}
          </button>
        </div>
        {error && <p className="dialog__error">{error}</p>}
        <div className="dialog__actions">
          <button type="button" className="btn" onClick={onClose}>
            {t('gallery.close')}
          </button>
          <button type="submit" className="btn btn--blue" disabled={busy}>
            {busy ? t('logo.drawing') : logos.length ? t('logo.again') : t('logo.draw')}
          </button>
        </div>
      </form>

      {logos.length > 0 && (
        <div className="logos">
          <p className="dialog__text">{t('logo.hint')}</p>
          {logos.map((svg, i) => (
            <div key={i} className="logos__item">
              <div className={`logos__preview${shownDark ? ' logos__preview--dark' : ''}`}>
                <img src={dataUri(svg)} alt={t('logo.option', { n: i + 1 })} />
              </div>
              <div className="logos__buttons">
                <a className="btn btn--small" href={dataUri(svg)} download={`logo-${i + 1}.svg`}>
                  {t('logo.download')}
                </a>
                <button type="button" className="btn btn--small btn--blue" disabled={applying !== null} onClick={() => apply(i)}>
                  {applying === i ? t('logo.applying') : t('logo.use')}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Dialog>
  )
}
