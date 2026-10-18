import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { useT } from '../i18n'

type Person = {
  email: string
  owner: boolean
  joined: string | null
  last_active: string | null
  sites: number
  generations: number
}

type Overview = {
  users: { total: number; new_7d: number; active_7d: number }
  sites: { total: number; published: number }
  generations: { today: number; last_7d: number; last_30d: number; total: number }
  models_7d: { model: string; count: number }[]
  photos: { total: number }
  people: Person[]
}

// How VibeForge is used — only the owner's accounts get the numbers.
export default function Stats() {
  const t = useT()
  const [data, setData] = useState<Overview | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch('/api/stats')
      .then(async (res) => {
        if (res.status === 403) throw new Error('stats.forbidden')
        if (!res.ok) throw new Error('error.generic')
        setData(await res.json())
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'error.generic'))
  }, [])

  const when = (iso: string | null) =>
    iso
      ? new Date(iso).toLocaleString(t.lang === 'uk' ? 'uk-UA' : 'en-GB', {
          day: 'numeric',
          month: 'short',
          hour: '2-digit',
          minute: '2-digit',
        })
      : '—'
  const topModel = data?.models_7d[0]?.count ?? 1

  return (
    <article className="legal stats card">
      <a href="/">{t('stats.back')}</a>
      <h2>{t('stats.title')}</h2>
      {error && <p className="stats__error">{error === 'stats.forbidden' ? t('stats.forbidden') : t('error.generic')}</p>}
      {!data && !error && <p>{t('gallery.loading')}</p>}
      {data && (
        <>
          <div className="stats__cards">
            <Card label={t('stats.users')} value={data.users.total}>
              {t('stats.usersDetail', { new: data.users.new_7d, active: data.users.active_7d })}
            </Card>
            <Card label={t('stats.sites')} value={data.sites.total}>
              {t('stats.sitesDetail', { published: data.sites.published })}
            </Card>
            <Card label={t('stats.generationsToday')} value={data.generations.today}>
              {t('stats.generationsDetail', {
                week: data.generations.last_7d,
                month: data.generations.last_30d,
                total: data.generations.total,
              })}
            </Card>
            <Card label={t('stats.photos')} value={data.photos.total} />
          </div>

          <h3>{t('stats.models')}</h3>
          {data.models_7d.length === 0 ? (
            <p className="stats__muted">—</p>
          ) : (
            <ul className="stats__models">
              {data.models_7d.map((m) => (
                <li key={m.model}>
                  <span className="stats__model">{m.model}</span>
                  <span className="stats__bar" aria-hidden="true">
                    <span style={{ width: `${(m.count / topModel) * 100}%` }} />
                  </span>
                  <span className="stats__count">{m.count}</span>
                </li>
              ))}
            </ul>
          )}

          <h3>{t('stats.people')}</h3>
          <div className="stats__table-wrap">
            <table className="stats__table">
              <thead>
                <tr>
                  <th>{t('stats.email')}</th>
                  <th>{t('stats.sites')}</th>
                  <th>{t('stats.generations')}</th>
                  <th>{t('stats.lastActive')}</th>
                </tr>
              </thead>
              <tbody>
                {data.people.map((p, i) => (
                  <tr key={i}>
                    <td>
                      {p.email}
                      {p.owner && <span className="stats__you">{t('stats.you')}</span>}
                    </td>
                    <td>{p.sites}</td>
                    <td>{p.generations}</td>
                    <td>{when(p.last_active)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="stats__muted">{t('stats.note')}</p>
        </>
      )}
    </article>
  )
}

function Card({ label, value, children }: { label: string; value: number; children?: React.ReactNode }) {
  return (
    <div className="stats__card">
      <span className="stats__label">{label}</span>
      <span className="stats__value">{value}</span>
      {children && <span className="stats__detail">{children}</span>}
    </div>
  )
}
