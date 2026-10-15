import { FormEvent, useState } from 'react'
import { supabase } from '../supabase'
import { Key, useT } from '../i18n'
import Mascot from './Mascot'

// signin  — email + password
// signup  — email + new password, then a code arrives by email
// confirm — enter that code to finish signing up
// forgot  — ask for a password-reset code
// reset   — enter the reset code + a new password
type Mode = 'signin' | 'signup' | 'confirm' | 'forgot' | 'reset'

// Supabase's error codes we can explain in the person's language; any
// other error is shown as Supabase words it.
const AUTH_ERRORS: Record<string, Key> = {
  invalid_credentials: 'auth.invalidCredentials',
  otp_expired: 'auth.badCode',
  weak_password: 'auth.weakPassword',
  over_email_send_rate_limit: 'auth.rateLimit',
  over_request_rate_limit: 'auth.rateLimit',
  same_password: 'auth.samePassword',
}

export default function SignIn() {
  const t = useT()
  const auth = supabase!.auth
  const [mode, setMode] = useState<Mode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function go(next: Mode, message: string | null = null) {
    setMode(next)
    setError(null)
    setNotice(message)
    setCode('')
    if (next === 'reset') setPassword('')
  }

  // Runs one auth step, showing its error (if any) under the form. A
  // successful sign-in needs no handling here: App listens for the new
  // session and swaps this screen out.
  async function run(event: FormEvent | null, step: () => Promise<void>) {
    event?.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await step()
    } catch (e) {
      const known = e && typeof e === 'object' && 'code' in e ? AUTH_ERRORS[String(e.code)] : undefined
      setError(known ? t(known) : e instanceof Error ? e.message : t('error.generic'))
    } finally {
      setBusy(false)
    }
  }

  const signIn = (e: FormEvent) =>
    run(e, async () => {
      const { error } = await auth.signInWithPassword({ email, password })
      if (error?.code === 'email_not_confirmed') {
        const resent = await auth.resend({ type: 'signup', email })
        if (resent.error) throw resent.error
        go('confirm', t('auth.notConfirmed', { email }))
        return
      }
      if (error) throw error
    })

  const signUp = (e: FormEvent) =>
    run(e, async () => {
      const { data, error } = await auth.signUp({ email, password })
      if (error) throw error
      // Supabase doesn't reveal whether an address is taken; an existing
      // account comes back as a user with no identities.
      if (data.user?.identities?.length === 0) {
        throw new Error(t('auth.alreadyRegistered'))
      }
      if (!data.session) go('confirm', t('auth.codeSent', { email }))
    })

  const confirm = (e: FormEvent) =>
    run(e, async () => {
      const { error } = await auth.verifyOtp({ email, token: code.trim(), type: 'signup' })
      if (error) throw error
    })

  const resendSignupCode = () =>
    run(null, async () => {
      const { error } = await auth.resend({ type: 'signup', email })
      if (error) throw error
      setNotice(t('auth.codeResent', { email }))
    })

  const sendResetCode = (e: FormEvent) =>
    run(e, async () => {
      const { error } = await auth.resetPasswordForEmail(email)
      if (error) throw error
      go('reset', t('auth.resetSent', { email }))
    })

  const resetPassword = (e: FormEvent) =>
    run(e, async () => {
      const verified = await auth.verifyOtp({ email, token: code.trim(), type: 'recovery' })
      if (verified.error) throw verified.error
      const updated = await auth.updateUser({ password })
      if (updated.error) throw updated.error
    })

  async function handleGoogle() {
    setError(null)
    const { error } = await auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin },
    })
    if (error) setError(error.message)
  }

  const emailField = (
    <input
      type="email"
      placeholder={t('auth.email')}
      aria-label={t('auth.email')}
      autoComplete="email"
      required
      value={email}
      onChange={(e) => setEmail(e.target.value)}
    />
  )
  const codeField = (
    <input
      type="text"
      placeholder={t('auth.code')}
      aria-label={t('auth.code')}
      inputMode="numeric"
      autoComplete="one-time-code"
      required
      value={code}
      onChange={(e) => setCode(e.target.value)}
    />
  )
  const passwordField = (autoComplete: string, placeholder: string) => (
    <input
      type="password"
      placeholder={placeholder}
      aria-label={placeholder}
      autoComplete={autoComplete}
      minLength={8}
      required
      value={password}
      onChange={(e) => setPassword(e.target.value)}
    />
  )
  const submit = (label: Key) => (
    <button type="submit" className="btn btn--orange btn--big" disabled={busy}>
      {t(label)}
    </button>
  )

  return (
    <section className="sign-in card">
      <Mascot size={52} />

      {mode === 'signin' && (
        <>
          <h2>{t('signin.title')}</h2>
          <p>{t('signin.intro')}</p>
          <form onSubmit={signIn}>
            {emailField}
            {passwordField('current-password', t('auth.password'))}
            {submit('signin.submit')}
          </form>
          <div className="sign-in__links">
            <button type="button" onClick={() => go('signup')}>{t('signin.toSignup')}</button>
            <button type="button" onClick={() => go('forgot')}>{t('signin.toForgot')}</button>
          </div>
        </>
      )}

      {mode === 'signup' && (
        <>
          <h2>{t('signup.title')}</h2>
          <p>{t('signup.intro')}</p>
          <form onSubmit={signUp}>
            {emailField}
            {passwordField('new-password', t('auth.newPassword'))}
            {submit('signup.submit')}
          </form>
          <div className="sign-in__links">
            <button type="button" onClick={() => go('signin')}>{t('signup.toSignin')}</button>
          </div>
        </>
      )}

      {mode === 'confirm' && (
        <>
          <h2>{t('confirm.title')}</h2>
          <form onSubmit={confirm}>
            {codeField}
            {submit('confirm.submit')}
          </form>
          <div className="sign-in__links">
            <button type="button" onClick={resendSignupCode} disabled={busy}>{t('confirm.resend')}</button>
            <button type="button" onClick={() => go('signin')}>{t('auth.back')}</button>
          </div>
        </>
      )}

      {mode === 'forgot' && (
        <>
          <h2>{t('forgot.title')}</h2>
          <p>{t('forgot.intro')}</p>
          <form onSubmit={sendResetCode}>
            {emailField}
            {submit('forgot.submit')}
          </form>
          <div className="sign-in__links">
            <button type="button" onClick={() => go('signin')}>{t('auth.back')}</button>
          </div>
        </>
      )}

      {mode === 'reset' && (
        <>
          <h2>{t('reset.title')}</h2>
          <form onSubmit={resetPassword}>
            {codeField}
            {passwordField('new-password', t('auth.resetPassword'))}
            {submit('reset.submit')}
          </form>
          <div className="sign-in__links">
            <button type="button" onClick={() => go('signin')}>{t('auth.back')}</button>
          </div>
        </>
      )}

      {notice && <p className="sign-in__notice">{notice}</p>}
      {error && <p className="sign-in__error">{error}</p>}

      {(mode === 'signin' || mode === 'signup') && (
        <>
          <div className="sign-in__divider">{t('auth.or')}</div>
          <button type="button" className="btn btn--big sign-in__google" onClick={handleGoogle}>
            {t('auth.google')}
          </button>
        </>
      )}
    </section>
  )
}
