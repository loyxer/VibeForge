import { FormEvent, useState } from 'react'
import { supabase } from '../supabase'

// signin  — email + password
// signup  — email + new password, then a code arrives by email
// confirm — enter that code to finish signing up
// forgot  — ask for a password-reset code
// reset   — enter the reset code + a new password
type Mode = 'signin' | 'signup' | 'confirm' | 'forgot' | 'reset'

export default function SignIn() {
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
      setError(e instanceof Error ? e.message : 'Something went wrong — try again.')
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
        go('confirm', `Your email isn't confirmed yet — we sent a new code to ${email}.`)
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
        throw new Error('This email is already registered — sign in instead.')
      }
      if (!data.session) go('confirm', `We sent a code to ${email}. It may take a minute.`)
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
      setNotice(`New code sent to ${email}.`)
    })

  const sendResetCode = (e: FormEvent) =>
    run(e, async () => {
      const { error } = await auth.resetPasswordForEmail(email)
      if (error) throw error
      go('reset', `If ${email} has an account, we sent it a code.`)
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
      placeholder="Email"
      autoComplete="email"
      required
      value={email}
      onChange={(e) => setEmail(e.target.value)}
    />
  )
  const codeField = (
    <input
      type="text"
      placeholder="Code from the email"
      inputMode="numeric"
      autoComplete="one-time-code"
      required
      value={code}
      onChange={(e) => setCode(e.target.value)}
    />
  )
  const passwordField = (autoComplete: string, placeholder = 'Password') => (
    <input
      type="password"
      placeholder={placeholder}
      autoComplete={autoComplete}
      minLength={8}
      required
      value={password}
      onChange={(e) => setPassword(e.target.value)}
    />
  )

  return (
    <section className="sign-in">
      {mode === 'signin' && (
        <>
          <h2>Sign in to start building</h2>
          <p>Your sites are saved to your account, so they're here next time you come back.</p>
          <form onSubmit={signIn}>
            {emailField}
            {passwordField('current-password')}
            <button type="submit" disabled={busy}>Sign in</button>
          </form>
          <div className="sign-in__links">
            <button type="button" onClick={() => go('signup')}>Create an account</button>
            <button type="button" onClick={() => go('forgot')}>Forgot password?</button>
          </div>
        </>
      )}

      {mode === 'signup' && (
        <>
          <h2>Create your account</h2>
          <p>We'll email you a code to confirm the address.</p>
          <form onSubmit={signUp}>
            {emailField}
            {passwordField('new-password', 'Password (at least 8 characters)')}
            <button type="submit" disabled={busy}>Create account</button>
          </form>
          <div className="sign-in__links">
            <button type="button" onClick={() => go('signin')}>I already have an account</button>
          </div>
        </>
      )}

      {mode === 'confirm' && (
        <>
          <h2>Check your email</h2>
          <form onSubmit={confirm}>
            {codeField}
            <button type="submit" disabled={busy}>Confirm</button>
          </form>
          <div className="sign-in__links">
            <button type="button" onClick={resendSignupCode} disabled={busy}>Send a new code</button>
            <button type="button" onClick={() => go('signin')}>Back to sign in</button>
          </div>
        </>
      )}

      {mode === 'forgot' && (
        <>
          <h2>Reset your password</h2>
          <p>We'll email you a code to set a new one.</p>
          <form onSubmit={sendResetCode}>
            {emailField}
            <button type="submit" disabled={busy}>Send code</button>
          </form>
          <div className="sign-in__links">
            <button type="button" onClick={() => go('signin')}>Back to sign in</button>
          </div>
        </>
      )}

      {mode === 'reset' && (
        <>
          <h2>Set a new password</h2>
          <form onSubmit={resetPassword}>
            {codeField}
            {passwordField('new-password', 'New password (at least 8 characters)')}
            <button type="submit" disabled={busy}>Save and sign in</button>
          </form>
          <div className="sign-in__links">
            <button type="button" onClick={() => go('signin')}>Back to sign in</button>
          </div>
        </>
      )}

      {notice && <p className="sign-in__notice">{notice}</p>}
      {error && <p className="sign-in__error">{error}</p>}

      {(mode === 'signin' || mode === 'signup') && (
        <>
          <div className="sign-in__divider">or</div>
          <button type="button" className="sign-in__google" onClick={handleGoogle}>
            Continue with Google
          </button>
        </>
      )}
    </section>
  )
}
