# Backlog - agents7 UI

### 2026.10.25 (global Svelte rule changed)

- [ ] Log a failed `/api/info` with `console.warn` in
  `frontend/src/App.svelte` (the `$effect` around line 66). Today
  `.catch(() => {})` hides a network error, and `r.ok ? r.json() : null`
  hides an error response, so the sidebar shows no version with no
  reason given. The global Svelte rule's *App name and version* section
  now asks for the warning (changed 25th October 2026). (LOW, S)

### Layout — 4th October 2026

- [ ] Decide whether the Runner page's form, output card and steps
  list keep their 700px width. v0.45.2 removed the width limit from
  prose on every page, but `.setup`, `.output-card` and
  `.steps-section` in `frontend/src/pages/Runner.svelte` are
  containers, not prose, and were left alone. The agent description
  sits inside `.setup`, so on a 1920px window it still wraps at 700px
  with the right half of the page empty. Removing the limit makes the
  inputs 1350px wide; the alternative is to limit the inputs only.
  The operator's call. (LOW, S)
- [ ] **[manual]** Look at the rebuilt block above a read's
  conversation and say whether it is what you wanted. Shipped in
  v0.46.0 after the operator asked for it to be "more stylish" and
  better organised: four sections (Run, Context, Knew already,
  Variants), label above value, long values on a row of their own,
  the facts as a list. Open any read on the Reads page,
  `http://localhost:5186/#/reads`, with the dev server up. The layout is tested; how it looks is the
  operator's call. (LOW, S)

### Config — 12th July 2026

- [ ] Set `ANTHROPIC_API_KEY` in `agents7_ui/.env` so the Chatter page's
  Anthropic provider override can be used. Until set, Anthropic shows as
  "not ready" on the Chatter page. `OPENAI_COMPAT_API_KEY` is set (DeepSeek,
  23rd August 2026). (LOW, S)
