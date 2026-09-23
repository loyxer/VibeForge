import { createClient } from '@supabase/supabase-js'

// Set VITE_SUPABASE_URL + VITE_SUPABASE_PUBLISHABLE_KEY (Vercel env vars, or
// frontend/.env.local locally) to turn on Google sign-in. Without them the
// app runs with no accounts at all, matching a backend that has no Supabase
// keys either.
const url = import.meta.env.VITE_SUPABASE_URL
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY

export const supabase = url && key ? createClient(url, key) : null
