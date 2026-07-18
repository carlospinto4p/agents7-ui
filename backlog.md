
# Backlog - agents7 UI

### Tool agents — 18th July 2026

- [ ] Support tool agents in the run and eval endpoints. Both currently
  refuse them with a 422 (`reject_tool_agent`, v0.27.1) because they
  read `response.model`, which a `ToolAgent` never populates. Serving
  them means running the trajectory route (`run_eval_suite` scores them
  since agents7 v4.14.0) and rendering the new shape: the tool-call
  sequence per row, per-tool recall, and missing/extra calls in place
  of the confusion matrix. The run endpoint additionally needs a
  free-text answer view plus the intermediate `ToolStepEvent`s, which
  `act_stream` already yields. (MED, L)

### Config — 12th July 2026

- [ ] Set the provider API keys in `agents7_ui/.env` so the Chatter page's provider override can use them: `ANTHROPIC_API_KEY` (Anthropic) and `OPENAI_COMPAT_API_KEY` or `OPENAI_API_KEY` (openai_compat). Until set, those providers show as "not ready" on the Chatter page. (LOW, S)

