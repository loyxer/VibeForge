// The two legal pages, /privacy and /terms. Plain text on purpose: they
// should say what the code actually does, so update them whenever a new
// service or kind of data is added.

import type { ReactNode } from 'react'

const CONTACT = 'vibeforge.verify@gmail.com'
const UPDATED = 'October 15, 2026'

function Page({ title, children }: { title: string; children: ReactNode }) {
  return (
    <article className="legal">
      <a href="/">← Back to VibeForge</a>
      <h2>{title}</h2>
      <p className="legal__updated">Last updated: {UPDATED}</p>
      {children}
      <h3>Contact</h3>
      <p>
        Questions or requests: <a href={`mailto:${CONTACT}`}>{CONTACT}</a>
      </p>
    </article>
  )
}

export function Privacy() {
  return (
    <Page title="Privacy Policy">
      <p>
        VibeForge is an independent project run by a single developer. It turns a text
        description into a one-page website. This page explains what data the service
        handles and why.
      </p>

      <h3>What we collect</h3>
      <ul>
        <li>
          <strong>Your account.</strong> Your email address. If you sign in with Google, also
          the name and profile picture Google shares. If you sign up with a password, it is
          stored only in hashed form; we never see it.
        </li>
        <li>
          <strong>What you create.</strong> The prompts you type and the websites generated
          from them, so your projects are there when you come back.
        </li>
        <li>
          <strong>Usage records.</strong> The time of each generation and which AI model made
          it. This is how the daily limit is counted.
        </li>
        <li>
          <strong>Technical logs.</strong> Like any website, our hosting providers record
          requests (including IP addresses) for security and troubleshooting.
        </li>
      </ul>
      <p>
        We do not use advertising or analytics trackers. Your browser stores a sign-in token
        so you stay signed in.
      </p>

      <h3>Who processes it</h3>
      <ul>
        <li><strong>Supabase</strong> stores accounts and projects (servers in the EU, Ireland).</li>
        <li><strong>Render</strong> runs our server (USA) and <strong>Vercel</strong> serves the site.</li>
        <li>
          <strong>Google Gemini</strong> generates the websites: your prompt and the current
          version of your site are sent to Google. We use Google's free tier, where Google may
          use this content to improve its products and human reviewers may read it.{' '}
          <strong>Do not put personal or confidential information in prompts.</strong>
        </li>
        <li><strong>Gmail</strong> sends the sign-in and password-reset codes.</li>
        <li>
          <strong>Unsplash</strong> provides the photos: our server sends it only the short photo
          descriptions the AI writes (like "latte art on a wooden table"), never your account
          details. Generated and published sites load those photos from Unsplash's servers.
        </li>
      </ul>
      <p>We do not sell your data or share it with anyone else.</p>

      <h3>Published sites</h3>
      <p>
        When you publish a site, anyone with its link can see it, without signing in. Your name
        and email are not shown on it. Unpublish it or delete the project to take it down.
      </p>

      <h3>How long we keep it</h3>
      <p>
        Until you delete it. You can delete any project in the app. To delete your whole
        account and everything in it, email us and we will do it within 30 days.
      </p>

      <h3>Your rights</h3>
      <p>
        You can ask for a copy of your data, a correction, or deletion at any time by
        emailing us. If you are in the EU you also have the right to complain to your data
        protection authority.
      </p>

      <h3>Children</h3>
      <p>VibeForge is not intended for children under 16.</p>
    </Page>
  )
}

export function Terms() {
  return (
    <Page title="Terms of Service">
      <p>By using VibeForge you agree to these terms.</p>

      <h3>The service</h3>
      <p>
        VibeForge generates one-page websites from text descriptions using AI. It is a free
        service in early development, provided as is: it may be slow, unavailable, or change
        at any time, and limits (currently 5 generations per day) may change.
      </p>

      <h3>What you create</h3>
      <p>
        The websites you generate are yours to use. AI output can contain mistakes and may
        resemble what other people generate, so review a site before you publish it. You are
        responsible for how you use it.
      </p>

      <h3>Rules</h3>
      <ul>
        <li>Do not generate illegal content, phishing or scam pages, malware, or sites that impersonate real people or organisations.</li>
        <li>Do not try to get around the limits, for example with multiple accounts.</li>
        <li>Do not attack or overload the service.</li>
      </ul>
      <p>We may suspend accounts that break these rules.</p>

      <h3>Liability</h3>
      <p>
        To the extent the law allows, VibeForge is not liable for losses resulting from the
        use of the service or of the websites it generates.
      </p>

      <h3>Changes</h3>
      <p>
        We may update these terms; the date at the top shows the latest version. See also
        our <a href="/privacy">Privacy Policy</a>.
      </p>
    </Page>
  )
}
