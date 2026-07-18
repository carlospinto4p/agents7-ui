# agents7-ui Roadmap

The standing direction for development sessions. `backlog.md` holds the
*items*; this file holds the *ordering, gates, and invariants* that decide
which items to pick and which to refuse. Consult it **before selecting work**.

**Maintenance:** update when a direction-level decision lands, when a gate
clears, or when a phase completes. Keep it short — ordering and gates only;
rationale lives in the docs or ADRs it cites.

## Current phase: follow the framework's measurement phase

1. **Make the Eval page a first-class consumer of `agents7.eval`.**
   `backend/routers/eval.py` runs a golden set and returns metrics, but
   the framework roadmap's phase 1 is composing eval data → run →
   metrics → report into one documented route, and this UI is the
   natural surface for it.
   **Gate: no eval feature here that duplicates framework logic —
   extend `agents7.eval` and call it.**
2. **Then resume page and feature work.**

## Standing invariants (apply to every session)

- **Interactive and render-level frontend behaviour ships with an e2e
  test.** The Playwright harness exists as of v0.27.0 — `e2e/` specs
  stub every `/api` boundary, so there is no longer an excuse to
  verify a feature by build plus manual check alone.
- **The UI is a thin view over the framework.** No agent logic in
  `backend/routers/`. Pages introspect the installed framework
  (`BaseAgent.__subclasses__()`, dataclass fields, docstrings) rather
  than carry a hardcoded list, so they track it automatically.
- **Provider-agnostic by default.** A feature landing for one of
  Ollama / Anthropic / OpenAI-compat either works across all three or
  states explicitly why it is scoped to one.
- **The backend is never host-exposed in Compose** — it is reachable
  only from nginx inside the Docker network (v0.7.3).
- **Host ports stay registry-claimed** — 5185 for the Compose frontend,
  5186 for the Vite dev server. Never a framework default.
- **`logs/warnings/` and `logs/errors/` hold first-party backend
  records only.** nginx and other third-party containers stay on
  `docker compose logs`.
- **17px floor on raw text**; badges and compact chips are exempt.

## What NOT to do (recent refuted directions)

- **Don't put the version badge in or above the top bar.** It enlarged
  the header and broke its layout; the badge lives in the `Home` page
  intro instead (v0.10.1).
- **Don't add a second source of the app version.**
  `frontend/package.json`'s `version` drifted from the canonical value
  and was read by nothing; `/api/info`, sourced from
  `backend/pyproject.toml`, is the only source.
- **Don't let a `$effect` call helpers that read `$state`.** The leaked
  reactive dependency re-fires the effect on every flag change and
  cascades API calls into 429s — see
  `.claude/rules/improvement-areas.md`.
