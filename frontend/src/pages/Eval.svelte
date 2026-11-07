<script>
  import { downloadJson, fmtCost, retryLabel } from '../lib/format.js'

  let agents = $state([])
  let selectedAgent = $state('')
  let result = $state(null)
  let loading = $state(false)
  let error = $state(null)

  let selectedSummary = $derived(
    agents.find(a => a.name === selectedAgent) ?? null
  )

  $effect(() => {
    fetch('/api/catalog')
      .then(r => r.json())
      .then(d => {
        agents = d
        if (d.length > 0) selectedAgent = d[0].name
      })
      .catch(() => {})
  })

  async function runEval() {
    if (!selectedAgent) return
    loading = true
    error = null
    result = null
    try {
      const res = await fetch(`/api/eval/${encodeURIComponent(selectedAgent)}`, {
        method: 'POST'
      })
      if (!res.ok) {
        const body = await res.json()
        throw new Error(body.detail || `HTTP ${res.status}`)
      }
      result = await res.json()
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
  }

  function pct(n, d) {
    return d > 0 ? Math.round((n / d) * 100) : 0
  }

  function fmt(val) {
    if (val === null || val === undefined) return '—'
    if (typeof val === 'object') return JSON.stringify(val)
    return String(val)
  }

  function accuracyColor(ratio) {
    if (ratio === 1) return 'green'
    if (ratio >= 0.7) return 'yellow'
    return 'red'
  }

  // A tool agent is scored on its trajectory, so the run carries a
  // `trajectory` block instead of the per-category breakdown.
  let trajectory = $derived(result?.trajectory ?? null)

  let perToolRows = $derived(
    Object.entries(trajectory?.per_tool ?? {})
      .map(([name, stats]) => ({
        name,
        ...stats,
        recall: stats.expected > 0 ? stats.matched / stats.expected : 0,
      }))
      .sort((a, b) => a.recall - b.recall),
  )

  // Accuracy per output field, worst first — a run can score well
  // overall while one field is carrying the others.
  //
  // A tool agent is scored on one synthetic field holding its whole
  // trajectory, so its per-field table would be a single row saying
  // what the trajectory block above already says. Omit it there.
  let perFieldRows = $derived(
    trajectory
      ? []
      : Object.entries(result?.per_field ?? {})
          .map(([name, accuracy]) => ({ name, accuracy }))
          .sort((a, b) => a.accuracy - b.accuracy),
  )

  // What the run cost, in one line:
  // "12 calls · 4,320 tok · 41.2s (3.4s avg, 1.5–6.0s) · $0.0034".
  //
  // A run is measured in LLM calls, not rows — `run_evaluation`
  // batches, so ten rows can be one call. The spread is shown only
  // when there was more than one call to compare.
  //
  // An agent that makes no LLM call at all — a rule-based one —
  // reports no calls, and the line is omitted rather than rendered
  // as a run of zero.
  let callsLine = $derived.by(() => {
    const c = result?.calls
    if (!c) return ''
    const t = result?.timing
    const parts = [`${c.calls} ${c.calls === 1 ? 'call' : 'calls'}`]
    if (c.tokens || c.prompt_tokens) {
      parts.push(`${(c.tokens + c.prompt_tokens).toLocaleString()} tok`)
    }
    let time = `${c.total_duration.toFixed(1)}s`
    if (c.calls > 1) {
      time += ` (${c.avg_duration.toFixed(1)}s avg`
      if (t) time += `, ${t.min_s.toFixed(1)}–${t.max_s.toFixed(1)}s`
      time += ')'
    }
    parts.push(time)
    // An unpriced run is not a free one, so it says so in words
    // rather than showing $0.00.
    parts.push(
      c.cost_cents == null ? 'unpriced' : fmtCost(c.cost_cents) || '$0.00',
    )
    if (c.cached_calls) parts.push(`${c.cached_calls} cached`)
    const retries = retryLabel(c)
    if (retries) parts.push(retries)
    return parts.join(' · ')
  })

  // The rows the agent never answered, as opposed to answered
  // wrongly. Counted separately because an accuracy that folds
  // them in is reporting a broken run as a bad one.
  let erroredCount = $derived(
    (result?.mismatches ?? []).filter(m => m.error).length,
  )
</script>

<div class="eval-page">
  <div class="page-header">
    <h2>Evaluation</h2>
    <p class="intro-desc">Measures accuracy against a golden dataset — curated inputs with known expected outputs. Results include an overall score, accuracy per output field, a per-category breakdown, what the run cost in calls, tokens, time and money, and a mismatch list for every failure. A tool agent is scored on its trajectory instead: which tools it called, in what order, with which arguments.</p>
  </div>

  <div class="controls">
    <select bind:value={selectedAgent} disabled={loading}>
      {#each agents as a}
        <option value={a.name}>{a.name}</option>
      {/each}
    </select>
    <button onclick={runEval} disabled={loading || !selectedAgent}>
      {loading ? 'Running…' : 'Run Eval'}
    </button>
    {#if result}
      <button
        class="dl-btn"
        onclick={() => downloadJson(`${selectedAgent}-eval.json`, result)}
      >⬇ JSON</button>
    {/if}
  </div>

  {#if selectedSummary?.description}
    <p class="agent-desc">{selectedSummary.description}</p>
  {/if}

  {#if error}
    <p class="msg error">Error: {error}</p>
  {/if}

  {#if result}
    <section class="summary">
      <div class="accuracy-header">
        <span class="accuracy-label">Accuracy</span>
        <span class="accuracy-value">
          {pct(result.passed, result.total)}%
          <span class="muted">({result.passed}/{result.total})</span>
        </span>
      </div>
      <div class="accuracy-bar">
        <div
          class="accuracy-fill {accuracyColor(result.accuracy)}"
          style="width: {pct(result.passed, result.total)}%"
        ></div>
      </div>
      <p class="meta">
        Golden set: <span class="mono">{result.golden_set}</span>
        · {result.total} entries
        · {result.failed} failed
        {#if erroredCount > 0}
          · <span class="errored">{erroredCount} never answered</span>
        {/if}
        {#if result.model}
          · <span class="mono">{result.model}</span>
        {/if}
      </p>
      {#if callsLine}
        <p class="meta" data-testid="eval-calls">{callsLine}</p>
      {/if}
    </section>

    {#if trajectory}
      <section data-testid="trajectory-summary">
        <h3>Trajectory</h3>
        <p class="meta traj-meta">
          Match mode: <span class="mono">{trajectory.mode}</span>
          · {trajectory.matched_calls}/{trajectory.expected_calls} expected calls made
          ({pct(trajectory.matched_calls, trajectory.expected_calls)}%)
          · {trajectory.extra_calls} extra
          · {trajectory.failed_calls ?? 0} rejected
        </p>

        {#if perToolRows.length > 0}
          <table>
            <thead>
              <tr>
                <th>Tool</th>
                <th>Matched</th>
                <th>Expected</th>
                <th>Recall</th>
              </tr>
            </thead>
            <tbody>
              {#each perToolRows as row}
                <tr>
                  <td class="mono">{row.name}</td>
                  <td>{row.matched}</td>
                  <td>{row.expected}</td>
                  <td>
                    <span class="badge {accuracyColor(row.recall)}">
                      {pct(row.matched, row.expected)}%
                    </span>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </section>
    {/if}

    {#if perFieldRows.length > 0}
      <section data-testid="per-field">
        <h3>Per-field</h3>
        <p class="meta">
          How often each output field matched, across all
          {result.total} entries. A row passes only when every field
          does, so overall accuracy is never higher than the worst
          field here.
        </p>
        <table>
          <thead>
            <tr>
              <th>Field</th>
              <th>Accuracy</th>
            </tr>
          </thead>
          <tbody>
            {#each perFieldRows as row}
              <tr>
                <td class="mono">{row.name}</td>
                <td>
                  <span class="badge {accuracyColor(row.accuracy)}">
                    {Math.round(row.accuracy * 100)}%
                  </span>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </section>
    {/if}

    {#if Object.keys(result.per_category).length > 0}
      <section>
        <h3>Per-category</h3>
        <table>
          <thead>
            <tr>
              <th>Category</th>
              <th>Passed</th>
              <th>Total</th>
              <th>Accuracy</th>
            </tr>
          </thead>
          <tbody>
            {#each Object.entries(result.per_category).sort((a, b) => a[1].accuracy - b[1].accuracy) as [cat, stats]}
              <tr>
                <td class="mono">{cat}</td>
                <td>{stats.passed}</td>
                <td>{stats.total}</td>
                <td>
                  <span class="badge {accuracyColor(stats.accuracy)}">
                    {pct(stats.passed, stats.total)}%
                  </span>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </section>
    {/if}

    {#if result.mismatches.length > 0}
      <section>
        <h3>Mismatches <span class="count">({result.mismatches.length})</span></h3>
        <div class="mismatches">
          {#each result.mismatches as m, i}
            <div class="mismatch">
              <div class="mismatch-num">#{i + 1}</div>
              <div class="mismatch-body">
                <div class="mismatch-row">
                  <span class="label">Input</span>
                  <span class="mono">{fmt(m.input)}</span>
                </div>
                {#if trajectory}
                  <div class="mismatch-row">
                    <span class="label">Called</span>
                    <span class="mono">{m.called.length > 0 ? m.called.join(' → ') : '—'}</span>
                  </div>
                  {#if m.missing.length > 0}
                    <div class="mismatch-row">
                      <span class="label">Missing</span>
                      <span class="mono actual">{m.missing.join(', ')}</span>
                    </div>
                  {/if}
                  {#if m.extra.length > 0}
                    <div class="mismatch-row">
                      <span class="label">Extra</span>
                      <span class="mono actual">{m.extra.join(', ')}</span>
                    </div>
                  {/if}
                  {#if m.error}
                    <div class="mismatch-row">
                      <span class="label">Error</span>
                      <span class="mono actual">{m.error}</span>
                    </div>
                  {/if}
                {:else}
                  <div class="mismatch-row">
                    <span class="label">Expected</span>
                    <span class="mono expected">{fmt(m.expected)}</span>
                  </div>
                  {#if m.error}
                    <!-- The agent never answered this row. Showing
                         "Actual —" instead would read as a confident
                         empty answer rather than a failed call. -->
                    <div class="mismatch-row">
                      <span class="label">Error</span>
                      <span class="mono actual">{m.error}</span>
                    </div>
                  {:else}
                    <div class="mismatch-row">
                      <span class="label">Actual</span>
                      <span class="mono actual">{fmt(m.actual)}</span>
                    </div>
                  {/if}
                {/if}
              </div>
            </div>
          {/each}
        </div>
      </section>
    {:else if result.total > 0}
      <p class="msg muted">All {result.total} entries passed.</p>
    {/if}
  {/if}
</div>

<style>
  .eval-page { max-width: 860px; margin: 0 auto; }

  .page-header {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    margin-bottom: 1.5rem;
  }
  .page-header h2 { margin: 0; color: var(--text-strong); }
  .intro-desc {
    color: var(--text-muted);
    font-size: 1.0625rem;
    line-height: 1.6;
    margin: 0;
  }

  .controls {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    margin-bottom: 1.5rem;
  }

  .agent-desc {
    margin: -1rem 0 1.5rem;
    font-size: 1.0625rem;
    line-height: 1.5;
    color: var(--text-muted);
  }

  select {
    padding: 0.35rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: 4px;
    font-size: 1.0625rem;
    min-width: 200px;
    background: var(--bg-surface);
    color: var(--text);
  }
  select:disabled { opacity: 0.4; }

  button {
    padding: 0.35rem 0.9rem;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--bg-surface);
    color: var(--text);
    cursor: pointer;
    font-size: 1.0625rem;
  }
  button:disabled { opacity: 0.4; cursor: not-allowed; }
  button:hover:not(:disabled) { background: var(--bg-raised); }

  /* Summary */
  .summary {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1rem 1.25rem;
    margin-bottom: 1.5rem;
  }

  .accuracy-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 0.5rem;
  }
  .accuracy-label { font-weight: 600; font-size: 1.0625rem; color: var(--text-muted); }
  .accuracy-value { font-size: 1.5rem; font-weight: 700; color: var(--text-strong); }

  .accuracy-bar {
    height: 10px;
    background: var(--bg-raised);
    border-radius: 5px;
    overflow: hidden;
    margin-bottom: 0.75rem;
  }
  .accuracy-fill {
    height: 100%;
    border-radius: 5px;
    transition: width 0.4s ease;
  }
  .accuracy-fill.green  { background: var(--pass); }
  .accuracy-fill.yellow { background: var(--warn); }
  .accuracy-fill.red    { background: var(--fail); }

  .meta { margin: 0; font-size: 1.0625rem; color: var(--text-muted); }
  .traj-meta { margin-bottom: 0.75rem; line-height: 1.5; }

  /* Tables */
  section { margin-bottom: 1.75rem; }

  h3 {
    margin: 0 0 0.75rem;
    font-size: 1.0625rem;
    font-weight: 600;
    color: var(--text-strong);
  }
  .count { color: var(--text-muted); font-weight: 400; }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 1.0625rem;
  }
  th, td {
    padding: 0.5rem 0.75rem;
    text-align: left;
    border-bottom: 1px solid var(--border);
    color: var(--text);
  }
  th {
    background: var(--bg-raised);
    font-weight: 600;
    color: var(--text-muted);
    font-size: 1.0625rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .badge {
    display: inline-block;
    padding: 0.1rem 0.45rem;
    border-radius: 10px;
    font-size: 1.0625rem;
    font-weight: 600;
  }
  .badge.green  { background: var(--pass-bg); color: var(--pass); }
  .badge.yellow { background: var(--warn-bg); color: var(--warn); }
  .badge.red    { background: var(--fail-bg); color: var(--fail); }

  /* Mismatches */
  .mismatches { display: flex; flex-direction: column; gap: 0.75rem; }

  .mismatch {
    display: flex;
    gap: 0.75rem;
    border: 1px solid var(--border);
    border-radius: 5px;
    padding: 0.75rem;
    font-size: 1.0625rem;
    background: var(--bg-surface);
  }

  .mismatch-num {
    color: var(--text-muted);
    font-size: 1.0625rem;
    min-width: 24px;
    padding-top: 2px;
  }

  .mismatch-body { flex: 1; display: flex; flex-direction: column; gap: 0.3rem; }

  .mismatch-row {
    display: flex;
    gap: 0.5rem;
    align-items: baseline;
  }

  .label {
    font-size: 1.0625rem;
    font-weight: 600;
    color: var(--text-muted);
    min-width: 54px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .mono { font-family: monospace; font-size: 1.0625rem; word-break: break-all; color: var(--text); }
  .expected { color: var(--pass); }
  .actual   { color: var(--fail); }

  .msg { padding: 0.5rem 0; }
  .error { color: var(--fail); }
  .errored { color: var(--fail); }
  .muted { color: var(--text-muted); }
</style>
