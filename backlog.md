
# Backlog - agents7 UI

### Scan — 17th May 2026

#### Refactoring

- [x] Verify `Runner.svelte:37-46` and `Eval.svelte:8-16` for similar untracked `$effect` dependency on fetch — add explicit deps or `untrack()` (MED, S)
- [x] Extract duplicate agent type maps in `routers/run.py:6-11` and `routers/chat.py:17-23` into shared util (MED, S)
- [x] Extract session storage dicts in `routers/chat.py:26-31` (`_sessions`, `_session_times`, `_start_counts`) into a `SessionStore` class (MED, M)
- [x] Standardize error handling across routers — some raise `ValueError`, others `HTTPException` for same scenarios (MED, M)
- [x] Extract config loading (`yaml.safe_load` + `from_yaml()`) duplicated in `run.py:81-82` and `chat.py:68-69` (LOW, S)
