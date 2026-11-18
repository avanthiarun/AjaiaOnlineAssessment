/** Small blue document glyph used in lists. */
export function DocIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size * 0.75} height={size} viewBox="0 0 24 32" aria-hidden="true" className="doc-icon">
      <path d="M0 2a2 2 0 0 1 2-2h14l8 8v22a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2z" fill="#1a73e8" />
      <path d="M16 0l8 8h-6a2 2 0 0 1-2-2z" fill="#a1c2fa" />
      <path d="M5 14h14v2H5zm0 4h14v2H5zm0 4h10v2H5z" fill="#fff" />
    </svg>
  );
}
