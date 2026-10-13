// The ids must match STYLES in backend/app/generation/styles.py (a backend
// test checks this); the backend holds the actual instructions for the AI.
export const STYLES = [
  { id: 'minimal', label: 'Minimal' },
  { id: 'bold', label: 'Bold' },
  { id: 'neon', label: 'Dark neon' },
  { id: 'retro', label: 'Retro' },
  { id: 'elegant', label: 'Elegant' },
  { id: 'playful', label: 'Playful' },
]

type Props = {
  value: string | null // null = let the AI decide
  onChange: (style: string | null) => void
}

export default function StylePicker({ value, onChange }: Props) {
  const options = [{ id: null, label: 'Auto' }, ...STYLES]
  return (
    <div className="styles" role="radiogroup" aria-label="Style">
      {options.map((option) => (
        <button
          key={option.id ?? 'auto'}
          type="button"
          role="radio"
          aria-checked={value === option.id}
          className={`styles__option${value === option.id ? ' styles__option--active' : ''}`}
          onClick={() => onChange(option.id)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
