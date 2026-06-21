
# Backlog - agents7 UI

### Refactoring — 21st June 2026

- [x] Dedupe eval glue against the framework — `backend/routers/eval.py` now duplicates golden-set loading, row normalisation, and `AGENT_TYPE_MAP`, which landed as reusable public API in `agents7.eval` (`load_eval_rows`, `normalise_rows`, `model_output_fields`, `AGENT_TYPE_MAP`, `build_agent`) in framework v4.3.0. Replace the local copies with imports. (LOW, S)
- [x] Dedupe `routers/utils.py` `AGENT_TYPE_MAP` / `import_class` against the framework — `routers/run.py` still resolves agent types via the local `AGENT_TYPE_MAP` (a copy of `agents7.eval.AGENT_TYPE_MAP`) and builds agents via `import_class`, duplicating `resolve_agent_class` / `build_agent`. `run.py` special-cases a `pipeline` type, so keep that branch; replace only the structured-agent resolution with the framework helpers. (LOW, S)
