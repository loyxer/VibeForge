import { useState } from 'react'
import { supabase } from '../supabase'

export default function SignIn() {
  const [error, setError] = useState<string | null>(null)

  async function handleGoogle() {
    setError(null)
    const { error } = await supabase!.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin },
    })
    if (error) setError(error.message)
  }

  return (
    <section className="sign-in">
      <h2>Sign in to start building</h2>
      <p>Your sites are saved to your account, so they're here next time you come back.</p>
      <button type="button" className="sign-in__google" onClick={handleGoogle}>
        Continue with Google
      </button>
      {error && <p className="sign-in__error">{error}</p>}
    </section>
  )
}
