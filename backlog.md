
# Backlog - agents7 UI

### Scan findings — 2026.06.07

Refactoring:

- [x] `import_class` missing return type annotation (`backend/routers/utils.py:26`). (LOW, S)
- [x] Bare `except Exception` without logging in `_resolve_pipeline_step_details` (`backend/routers/catalog.py:87`) — log or narrow. (MED, S)

Frontend:

- [x] Catalog/Chatter top-level fetch `$effect` has no scoped dependencies and may re-run on unrelated state changes (`frontend/src/pages/Catalog.svelte`, `Chatter.svelte`) — verify against the `$effect`-leakage rule; scope with `untrack()` or move to an explicit on-mount call. (MED, S)

Test coverage:

- [ ] `import_class` and `_load_output_schema` error paths untested (`backend/routers/utils.py`) — missing module/class, malformed dotted path, ImportError/AttributeError suppression. (LOW, S)
