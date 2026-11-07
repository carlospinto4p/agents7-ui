# Optimization Areas

Project-specific performance areas to watch for when
running `/optimize` or noticing issues during normal work.

## Common Signals

- Sequential LLM calls that could be batched

## What to Look For

- **Memory**: unbounded growth, large object retention, unnecessary
  copies, missing cleanup/eviction
- **CPU**: hot loops, redundant computation, expensive operations in
  tight paths, regex compiled per call
- **I/O / Async**: sequential awaits that could use `asyncio.gather`,
  missing connection reuse, unbatched LLM calls
- **Data structures**: lists used for lookups (should be sets/dicts),
  string concatenation in loops, repeated serialization
- **Svelte UI**: expensive reactive computations, missing `$derived`
  for cached derived state, redundant API calls on re-render
- **Svelte 5 `$effect` leakage**: effects that call functions which
  read `$state` variables (e.g. `loading`, `starting`) register those
  as unintended dependencies — the effect re-fires on every flag
  change, cascading API calls and causing 429s. Fix with `untrack()`
  or replace with an explicit call at the triggering site.
