# agents7-ui Roadmap

The standing direction for development sessions. `backlog.md` holds the
*items*; this file holds the *ordering, gates, and invariants* that decide
which items to pick and which to refuse. Consult it **before selecting work**.

**Maintenance:** update when a direction-level decision lands, when a gate
clears, or when a phase completes. Keep it short — ordering and gates only;
rationale lives in the docs or ADRs it cites.

## Current phase: follow the framework's measurement phase

1. ~~**Make the Eval page a first-class consumer of
   `agents7.eval`.**~~ Shipped in v0.37.0: every agent type goes
   through `run_eval_suite`, and the page gained per-field
   accuracy, the run's calls/tokens/time/cost, and the
   error-versus-wrong-answer distinction. The two pieces it needed
   were added to the framework rather than to the router
   (`compute_per_category`, and a call summary that no longer
   requires a log file) — agents7 v4.38.0/v4.38.1. Gate cleared,
   but the standing invariant below keeps it enforced.
   **Standing gate: no eval feature here that duplicates framework
   logic — extend `agents7.eval` and call it.**
2. **Next: resume page and feature work.** No item of its own —
   this is the release valve for ordinary work now that step 1 has
   shipped, not a task.

## Standing invariants (apply to every session)

- **Interactive and render-level frontend behaviour ships with an e2e
  test.** The Playwright harness exists as of v0.27.0 — `e2e/` specs
  stub every `/api` boundary, so there is no longer an excuse to
  verify a feature by build plus manual check alone.
- **The UI is a thin view over the framework.** No agent logic in
  `backend/routers/`. Pages introspect the installed framework
  (`BaseAgent.__subclasses__()`, dataclass fields, docstrings) rather
  than carry a hardcoded list, so they track it automatically.
- **The Reads page edits `feedback.yml` and nothing else.** A read's
  `read.yml` — its verdicts and the notes anchored to a turn — is
  shown there and written in a text editor. Decided 2nd October
  2026: it is the judgement of a version and gets argued over in
  prose, which is a different job from attaching a correction.
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
