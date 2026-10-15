// Іскра (Spark): the little flame that "writes" the sites. Pure decoration —
// whatever she says is also in the text next to her.
export default function Mascot({ size = 34 }: { size?: number }) {
  return (
    <svg
      className="mascot"
      width={size}
      height={size * 1.1}
      viewBox="0 0 40 44"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M20 2C26 10 36 18 36 28a16 16 0 0 1-32 0C4 18 14 10 20 2z" fill="#ff9f1c" />
      <path d="M20 15c3 5 9 9 9 16a9 9 0 0 1-18 0c0-7 6-11 9-16z" fill="#ffd23f" />
      <circle cx="16" cy="29" r="2.6" fill="#2f2f2f" />
      <circle cx="24" cy="29" r="2.6" fill="#2f2f2f" />
      <circle cx="16.8" cy="28.2" r="0.9" fill="#fff" />
      <circle cx="24.8" cy="28.2" r="0.9" fill="#fff" />
      <path d="M17 34q3 2.6 6 0" fill="none" stroke="#2f2f2f" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  )
}
