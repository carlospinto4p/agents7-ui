# Improvement Areas

Project-specific areas to watch for when running
`/improvements` or noticing gaps during normal work.

## What to Look For

- **API gaps**: common workflows that require too many manual steps
- **New agent types**: patterns that don't fit existing agents
  (e.g., multi-turn, comparison, aggregation)
- **Provider support**: other LLM providers beyond Ollama
- **Output formats**: additional export/serialization options
- **Tooling**: CLI commands, debugging aids, profiling utilities
- **Resilience**: error recovery, graceful degradation, monitoring
- **Testing**: utilities that help users test their own agents
- **Documentation**: missing examples, guides, or tutorials

## Svelte 5 — `$effect` Dependency Leakage

When reviewing frontend code in `frontend/`, watch for `$effect`
blocks that call functions which internally read `$state` variables. Svelte 5
tracks every reactive read that happens synchronously inside an effect,
including through function calls. A helper that reads `loading`, `error`, or
any other piece of state becomes an **unintended dependency** — the effect
re-fires whenever that state changes, not just when the developer intended.

Classic sign: an effect that triggers an async operation, the async operation
toggles a boolean flag (`loading`, `starting`, `sending`, …), and the effect
re-runs on every flag change → infinite cascade, flooded API calls, 429s.

**Look for:**
- `$effect` bodies that call functions with `$state` reads in guard clauses
- Boolean flags (`starting`, `loading`, `sending`) read inside effect-called functions
- Effects that have no explicit dependency listed but implicitly depend on mutable state

**Fix pattern:** either call the function with `untrack(() => fn())` to opt
out of tracking, or replace the reactive effect with an explicit call at the
point where the triggering state is first set (e.g., inside a `.then()` or an
event handler).
