// Shared formatting and export helpers used across pages.

// Cost in cents (float) → "$0.0034", or '' when absent/zero. Local
// providers (Ollama) report no cost, so the empty string lets callers
// omit the part entirely.
export function fmtCost(cents) {
  if (cents == null || cents <= 0) return ''
  return `$${(cents / 100).toFixed(4)}`
}

// "123 tok · 1.2s · $0.0034" from a metrics object. Each part is
// included only when present.
export function metricsLine(m) {
  if (!m) return ''
  const parts = []
  if (m.tokens) parts.push(`${m.tokens} tok`)
  if (m.total_duration != null) parts.push(`${m.total_duration.toFixed(1)}s`)
  const cost = fmtCost(m.cost_cents)
  if (cost) parts.push(cost)
  return parts.join(' · ')
}

// Copy text to the clipboard; resolves true on success, false on
// failure (e.g. permissions denied or insecure context).
export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

// Trigger a browser download of `text` as `filename`.
export function downloadText(filename, text, mime = 'application/json') {
  const blob = new Blob([text], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// Convenience: download a value as pretty-printed JSON.
export function downloadJson(filename, value) {
  downloadText(filename, JSON.stringify(value, null, 2))
}
