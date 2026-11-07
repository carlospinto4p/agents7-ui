// Shared formatting and export helpers used across pages.

// Cost in cents (float) → "$0.000168", or '' when absent/zero. Local
// providers (Ollama) report no cost, so the empty string lets callers
// omit the part entirely.
//
// The precision is not decorative. A guarded chat turn costs a few
// hundredths of a cent, and the old fixed 4 decimal places rounded a
// real $0.000168 to "$0.0002" and anything under $0.00005 to
// "$0.0000" — a price that reads as free. Three significant digits
// with trailing zeros stripped keep a tiny number honest ("$0.000045")
// without padding a normal one ("$1.00", not "$1.0000").
export function fmtCost(cents) {
  if (cents == null || cents <= 0) return ''
  const dollars = cents / 100
  const decimals =
    dollars >= 1 ? 2 : Math.min(10, 2 - Math.floor(Math.log10(dollars)))
  const fixed = dollars.toFixed(decimals)
  // Keep at least two decimals, drop the zeros past the third digit.
  const trimmed =
    decimals > 2 ? fixed.replace(/(\.\d{2}\d*?)0+$/, '$1') : fixed
  return `$${trimmed}`
}

// "123 tok · 1.2s · $0.0034" from a metrics object, and for a guarded
// agent the guard's own cost and the turn total after it:
// "123 tok · 1.2s · $0.000168 + guard $0.000146 = $0.000314".
//
// A guarded reply is at least two LLM calls and only the first is in
// the reply's own metrics, so showing that figure alone understated a
// turn by about half. Each part is included only when present.
//
// A turn served from the response cache ends in "cached". Its token
// counts are the ones the original call was billed for and were not
// billed again, and its duration is the cache lookup rather than the
// model — so without the word, a cached turn reads as a real call
// that happened to be instant and free. When only the reply came
// from cache and the guard really ran, it says "reply cached", since
// half the turn was live and its price is on the line beside it.
export function metricsLine(m) {
  if (!m) return ''
  const parts = []
  if (m.tokens) parts.push(`${m.tokens} tok`)
  if (m.total_duration != null) parts.push(`${m.total_duration.toFixed(1)}s`)
  const cost = fmtCost(m.cost_cents)
  if (cost) parts.push(cost)
  const guard = fmtCost(m.guard?.cost_cents)
  if (cost && guard) {
    parts[parts.length - 1] = `${cost} + guard ${guard}`
    const total = fmtCost(m.total_cost_cents)
    if (total) parts[parts.length - 1] += ` = ${total}`
  }
  const cachedLabel = cacheLabel(m)
  if (cachedLabel) parts.push(cachedLabel)
  const retries = retryLabel(m)
  if (retries) parts.push(retries)
  return parts.join(' · ')
}

// 'cached' when every call in the turn was a cache hit, 'reply
// cached' when the guard still ran for real, '' when nothing was
// cached. A turn with no guard has only its own state to report.
export function cacheLabel(m) {
  if (!m?.cached) return ''
  if (m.guard && !m.guard.cached) return 'reply cached'
  return 'cached'
}

// '2 retries (4.3s)' when calls failed and were retried, '' when
// none did — which is the ordinary case, so the line stays as
// short as it was. Without this a run that spent minutes fighting
// rate limits looked identical to one that sailed through, with
// nothing on screen to explain the wait.
//
// A retried attempt raises before the provider reports anything,
// so it has no tokens and no price of its own — the seconds are
// the whole of what it cost, which is why they are shown and no
// cost is.
//
// The seconds are stated in brackets rather than as '+4.3s',
// because whether they are already counted in the duration next
// to them depends on the page. The Chatter line shows the
// framework's `total_duration`, which is the *successful*
// attempt's own figure, so there they are extra. The Runner and
// Catalog show a stopwatch the page itself ran, which was
// ticking throughout, so there they are included. One neutral
// wording is true in both places.
//
// For a guarded turn the guard's retries are added in, since both
// halves held the same person up.
export function retryLabel(m) {
  const retries = (m?.retries ?? 0) + (m?.guard?.retries ?? 0)
  if (!retries) return ''
  const seconds = (m?.retry_duration ?? 0) + (m?.guard?.retry_duration ?? 0)
  const label = `${retries} ${retries === 1 ? 'retry' : 'retries'}`
  return seconds > 0 ? `${label} (${seconds.toFixed(1)}s)` : label
}

// "42 tok · 1.2s · $0.0034 · cached · 1 retry +1.0s" for one
// pipeline step, on the Runner and Catalog pages. A step has no
// guard, so its cache state and its retries are its own.
export function stepMetaLine(m) {
  if (!m) return ''
  const parts = [`${m.tokens} tok`, `${m.total_duration?.toFixed(1)}s`]
  const cost = fmtCost(m.cost_cents)
  if (cost) parts.push(cost)
  const label = cacheLabel(m)
  if (label) parts.push(label)
  const retries = retryLabel(m)
  if (retries) parts.push(retries)
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
