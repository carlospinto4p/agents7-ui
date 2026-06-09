
# Backlog - agents7 UI

### 2026.06.09 (logging pattern)

- [ ] Logging: adopt the canonical file-based error/warning pattern (file-based error and warning logs). The `backend` service entry point (`agents7_ui/backend/main.py`) wires no file logging — routers use `getLogger(__name__)` (`routers/chat.py:14`, `routers/engine.py:12`). Add WARNING → `logs/warnings/` and ERROR → `logs/errors/` `RotatingFileHandler`s with a clean level split (WARNING-only filter on the warning handler), one file per process start, UTC timestamps; forward `uvicorn.error`. Gitignore `logs/`, bind-mount `./logs` in the root compose. Frontend is nginx (third-party) → `docker compose logs`. Optionally add `fix-errors`/`fix-warnings` skills. — MEDIUM — M

### Scan findings — 2026.06.07

Security:

- [ ] Path traversal in catalog pipeline-step resolution. `_resolve_pipeline_step_details` (`backend/routers/catalog.py:76`) builds `(config_file.parent / agent_ref).resolve()` from a pipeline YAML's `agent` field with **no** `relative_to(catalog_root)` guard — `run.py:21-23` has exactly that guard. A crafted pipeline config can read arbitrary YAML/JSON-parseable files and leak their contents in the API response. Mirror `run.py`'s `_resolve_agent_path` validation. (HIGH, S)

Performance:

- [ ] `/api/info` reads `pyproject.toml` from disk on every request (`backend/main.py:85`) — cache the version after first read (it never changes at runtime). (MED, S)
- [ ] `/api/readme` reads `README.md` on every request (`backend/main.py:73`) — cache the content. (LOW, S)
- [ ] Expired chat sessions are evicted only on demand in `_SessionStore` (`backend/routers/chat.py`); long-idle sessions linger. Consider periodic cleanup. (LOW, S)

Refactoring:

- [ ] `import_class` missing return type annotation (`backend/routers/utils.py:26`). (LOW, S)
- [ ] Bare `except Exception` without logging in `_resolve_pipeline_step_details` (`backend/routers/catalog.py:87`) — log or narrow. (MED, S)

Frontend:

- [ ] Catalog/Chatter top-level fetch `$effect` has no scoped dependencies and may re-run on unrelated state changes (`frontend/src/pages/Catalog.svelte`, `Chatter.svelte`) — verify against the `$effect`-leakage rule; scope with `untrack()` or move to an explicit on-mount call. (MED, S)

Test coverage:

- [ ] `import_class` and `_load_output_schema` error paths untested (`backend/routers/utils.py`) — missing module/class, malformed dotted path, ImportError/AttributeError suppression. (LOW, S)


### 2026.06.06

- [x] `frontend/package.json` version (`0.7.1`) is stale and drifts from the
  canonical app version in `backend/pyproject.toml` (`0.10.0`). Decide whether
  to keep it in sync on each release or drop the redundant version field.
  (Resolved v0.15.6 — dropped the redundant field; `private` package needs none.)
