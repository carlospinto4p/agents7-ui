
# Backlog - agents7 UI

### Scan findings — 2026.06.07

Test coverage:

- [x] `import_class` and `_load_output_schema` error paths untested (`backend/routers/utils.py`) — missing module/class, malformed dotted path, ImportError/AttributeError suppression. (LOW, S)
