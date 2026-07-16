
# Backlog - agents7 UI

### 2026.07.16 (roadmap)

- [ ] **Define this project's roadmap.** `roadmap.md` was scaffolded as
  an empty stub — its phase is a placeholder and its invariant and
  refuted-direction sections read `_None yet._`, so it currently records
  no direction and every consumer ignores it. Fill in the three
  sections: the **current phase** (the work in order, each step naming
  its gate where one applies — "no X before Y ships"), the **standing
  invariants** that hold whatever item is picked, and the **refuted
  directions** already tried and measured. Once filled,
  `/guided-backlog` recommends the earliest unmet step and refuses
  gate-blocked items, `/show-backlog` leads with the phase, and
  `/improvements` stops re-proposing refuted directions — until then all
  three fall back to recency. Keep it short: ordering and gates only,
  rationale stays in the docs or ADRs it cites. See the `roadmap` rule
  for the format. Priority: MEDIUM. Effort: Small.

### Config — 12th July 2026

- [ ] Set the provider API keys in `agents7_ui/.env` so the Chatter page's provider override can use them: `ANTHROPIC_API_KEY` (Anthropic) and `OPENAI_COMPAT_API_KEY` or `OPENAI_API_KEY` (openai_compat). Until set, those providers show as "not ready" on the Chatter page. (LOW, S)

### Testing — 12th July 2026

- [ ] Bootstrap a frontend test harness (Playwright e2e). The frontend has no automated tests, so interactive/render features ship verified only by build + manual check. First candidate to cover: sidebar drag-to-resize + width persistence added in v0.22.0. (MED, M)
