import { useEffect, useRef, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import type { Usage } from '../api'
import { supabase } from '../supabase'
import { Lang, useLang, useT } from '../i18n'
import Mascot from './Mascot'
import { ChangePasswordDialog, DeleteAccountDialog } from './AccountDialogs'

type Props = {
  session: Session | null
  usage: Usage | null
  // Only the workspace has a gallery to open.
  onOpenGallery?: () => void
}

export default function TopBar({ session, usage, onOpenGallery }: Props) {
  const t = useT()
  const left = usage?.remaining_today

  return (
    <header className="topbar">
      <a className="topbar__logo" href="/">
        <Mascot size={30} />
        <span>
          vibe<span className="topbar__logo-accent">forge</span>
        </span>
      </a>
      <div className="topbar__tools">
        {usage?.limit != null && left != null && (
          <div className="usage">
            {left === 0 ? (
              <span className="usage__label">{t('usage.none')}</span>
            ) : (
              <>
                <span className="usage__label">{t('usage.label')}</span>
                <span className="usage__bar" aria-hidden="true">
                  <span style={{ width: `${(left / usage.limit) * 100}%` }} />
                </span>
                <span className="usage__count">{t('usage.count', { left, limit: usage.limit })}</span>
              </>
            )}
          </div>
        )}
        {onOpenGallery && (
          <button type="button" className="btn btn--small" onClick={onOpenGallery}>
            {t('app.mySites')}
          </button>
        )}
        <LangSwitch />
        {session && <AccountMenu email={session.user.email ?? ''} />}
      </div>
    </header>
  )
}

function LangSwitch() {
  const { lang, setLang } = useLang()
  const t = useT()
  const options: { id: Lang; label: string }[] = [
    { id: 'uk', label: 'УКР' },
    { id: 'en', label: 'ENG' },
  ]
  return (
    <div className="lang" role="group" aria-label={t('app.language')}>
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          lang={o.id}
          aria-pressed={lang === o.id}
          className={`lang__option${lang === o.id ? ' lang__option--active' : ''}`}
          onClick={() => setLang(o.id)}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

function AccountMenu({ email }: { email: string }) {
  const t = useT()
  const [open, setOpen] = useState(false)
  const [dialog, setDialog] = useState<'password' | 'delete' | null>(null)
  const box = useRef<HTMLDivElement>(null)

  // Close on a click anywhere else or on Escape, like any menu.
  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className="account" ref={box}>
      <button
        type="button"
        className="account__button"
        aria-label={t('app.account')}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {email.charAt(0).toUpperCase() || '?'}
      </button>
      {open && (
        <div className="account__menu">
          <span className="account__email">{email}</span>
          <button
            type="button"
            className="btn btn--small"
            onClick={() => {
              setOpen(false)
              setDialog('password')
            }}
          >
            {t('account.changePassword')}
          </button>
          <button type="button" className="btn btn--small" onClick={() => supabase?.auth.signOut()}>
            {t('app.signOut')}
          </button>
          <button
            type="button"
            className="btn btn--small btn--danger"
            onClick={() => {
              setOpen(false)
              setDialog('delete')
            }}
          >
            {t('account.deleteTitle')}
          </button>
        </div>
      )}
      {dialog === 'password' && <ChangePasswordDialog onClose={() => setDialog(null)} />}
      {dialog === 'delete' && <DeleteAccountDialog onClose={() => setDialog(null)} />}
    </div>
  )
}
