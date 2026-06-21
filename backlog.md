
# Backlog - agents7 UI

### Refactoring — 21st June 2026

- [ ] Dedupe eval glue against the framework — `backend/routers/eval.py` now duplicates golden-set loading, row normalisation, and `AGENT_TYPE_MAP`, which landed as reusable public API in `agents7.eval` (`load_eval_rows`, `normalise_rows`, `model_output_fields`, `AGENT_TYPE_MAP`, `build_agent`) in framework v4.3.0. Replace the local copies with imports. (LOW, S)
