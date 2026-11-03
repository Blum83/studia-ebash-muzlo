import type { CSSProperties } from 'react'

export function fmt(sec: number) {
  const s = Math.round(sec)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

// Deterministic "cover art" from the track id.
export function coverStyle(id: string): CSSProperties {
  let h = 0
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0
  const a = h % 360
  const b = (a + 60 + ((h >> 9) % 120)) % 360
  return {
    background: `radial-gradient(circle at 30% 30%, hsl(${a} 80% 60%), transparent 60%),
      conic-gradient(from ${h % 360}deg, hsl(${a} 70% 35%), hsl(${b} 75% 45%), hsl(${a} 70% 35%))`,
  }
}
