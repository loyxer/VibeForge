import { FormEvent, useEffect, useRef, useState } from 'react'
import { apiFetch } from '../api'
import { supabase } from '../supabase'
import { useT } from '../i18n'

type DialogProps = { onClose: () => void }

// Shared frame: a small modal that closes on Escape or a click outside.
export function Dialog({
  title,
  onClose,
  children,
}: DialogProps & { title: string; children: React.ReactNode }) {
  const close = useRef(onClose)
  close.current = onClose
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && close.current()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])
  return (
    <div className="modal" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal__panel modal__panel--small card" role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal__head">
          <h2>{title}</h2>
        </div>
        {children}
      </div>
    </div>
  )
}

export function ChangePasswordDialog({ onClose }: DialogProps) {
  const t = useT()
  const [password, setPassword] = useState('')
  const [repeat, setRepeat] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (password.length < 8) return setError(t('auth.weakPassword'))
    if (password !== repeat) return setError(t('account.mismatch'))
    setBusy(true)
    const { error } = await supabase!.auth.updateUser({ password })
    setBusy(false)
    if (!error) return setDone(true)
    setError(
      error.code === 'same_password'
        ? t('auth.samePassword')
        : error.code === 'weak_password'
          ? t('auth.weakPassword')
          : error.message,
    )
  }

  return (
    <Dialog title={t('account.changePassword')} onClose={onClose}>
      {done ? (
        <>
          <p className="dialog__text">{t('account.passwordChanged')}</p>
          <div className="dialog__actions">
            <button type="button" className="btn btn--blue" onClick={onClose}>
              {t('gallery.close')}
            </button>
          </div>
        </>
      ) : (
        <form className="dialog__form" onSubmit={submit}>
          <input
            type="password"
            autoFocus
            autoComplete="new-password"
            placeholder={t('account.newPassword')}
            aria-label={t('account.newPassword')}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <input
            type="password"
            autoComplete="new-password"
            placeholder={t('account.repeatPassword')}
            aria-label={t('account.repeatPassword')}
            value={repeat}
            onChange={(e) => setRepeat(e.target.value)}
          />
          {error && <p className="dialog__error">{error}</p>}
          <div className="dialog__actions">
            <button type="button" className="btn" onClick={onClose}>
              {t('account.cancel')}
            </button>
            <button type="submit" className="btn btn--blue" disabled={busy}>
              {t('account.save')}
            </button>
          </div>
        </form>
      )}
    </Dialog>
  )
}

export function DeleteAccountDialog({ onClose }: DialogProps) {
  const t = useT()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function confirm() {
    setBusy(true)
    setError(null)
    try {
      const res = await apiFetch('/api/account', { method: 'DELETE' })
      if (!res.ok) throw new Error()
      // The session's user no longer exists; just forget it in this browser.
      await supabase?.auth.signOut({ scope: 'local' })
    } catch {
      setError(t('account.deleteFailed'))
      setBusy(false)
    }
  }

  return (
    <Dialog title={t('account.deleteTitle')} onClose={onClose}>
      <p className="dialog__text">{t('account.deleteWarning')}</p>
      {error && <p className="dialog__error">{error}</p>}
      <div className="dialog__actions">
        <button type="button" className="btn" onClick={onClose}>
          {t('account.cancel')}
        </button>
        <button type="button" className="btn btn--danger" disabled={busy} onClick={confirm}>
          {t('account.deleteConfirm')}
        </button>
      </div>
    </Dialog>
  )
}

const KINDS = ['idea', 'problem', 'question'] as const

export function FeedbackDialog({ email, onClose }: DialogProps & { email: string }) {
  const t = useT()
  const [kind, setKind] = useState<(typeof KINDS)[number]>('idea')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!message.trim()) return
    setBusy(true)
    setError(null)
    try {
      const res = await apiFetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind, message, email }),
      })
      if (res.status === 429) setError(t('feedback.tooMany'))
      else if (!res.ok) setError(t('feedback.failed'))
      else setDone(true)
    } catch {
      setError(t('feedback.failed'))
    }
    setBusy(false)
  }

  return (
    <Dialog title={t('feedback.title')} onClose={onClose}>
      {done ? (
        <>
          <p className="dialog__text">{t('feedback.sent')}</p>
          <div className="dialog__actions">
            <button type="button" className="btn btn--blue" onClick={onClose}>
              {t('gallery.close')}
            </button>
          </div>
        </>
      ) : (
        <form className="dialog__form" onSubmit={submit}>
          <p className="dialog__text">{t('feedback.intro')}</p>
          <div className="dialog__kinds" role="group">
            {KINDS.map((k) => (
              <button
                key={k}
                type="button"
                aria-pressed={kind === k}
                className={`chip${kind === k ? ' chip--active' : ''}`}
                onClick={() => setKind(k)}
              >
                {t(`feedback.${k}`)}
              </button>
            ))}
          </div>
          <textarea
            autoFocus
            rows={5}
            maxLength={2000}
            placeholder={t('feedback.placeholder')}
            aria-label={t('feedback.placeholder')}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
          />
          {error && <p className="dialog__error">{error}</p>}
          <div className="dialog__actions">
            <button type="button" className="btn" onClick={onClose}>
              {t('account.cancel')}
            </button>
            <button type="submit" className="btn btn--blue" disabled={busy || !message.trim()}>
              {t('feedback.send')}
            </button>
          </div>
        </form>
      )}
    </Dialog>
  )
}
