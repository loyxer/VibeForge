import { Key, useT } from '../i18n'

// The ids must match STYLES in backend/app/generation/styles.py (a backend
// test checks this); the backend holds the actual instructions for the AI.
export const STYLES: { id: string; label: Key }[] = [
  { id: 'minimal', label: 'style.minimal' },
  { id: 'bold', label: 'style.bold' },
  { id: 'neon', label: 'style.neon' },
  { id: 'retro', label: 'style.retro' },
  { id: 'elegant', label: 'style.elegant' },
  { id: 'playful', label: 'style.playful' },
]

type Props = {
  value: string | null // null = let the AI decide
  onChange: (style: string | null) => void
}

export default function StylePicker({ value, onChange }: Props) {
  const t = useT()
  const options = [{ id: null, label: 'style.auto' as Key }, ...STYLES]
  return (
    <div className="chips" role="radiogroup" aria-label={t('chat.style')}>
      {options.map((option) => (
        <button
          key={option.id ?? 'auto'}
          type="button"
          role="radio"
          aria-checked={value === option.id}
          className={`chip${value === option.id ? ' chip--active' : ''}`}
          onClick={() => onChange(option.id)}
        >
          <span className={`chip__swatch chip__swatch--${option.id ?? 'auto'}`} aria-hidden="true" />
          {t(option.label)}
        </button>
      ))}
    </div>
  )
}
