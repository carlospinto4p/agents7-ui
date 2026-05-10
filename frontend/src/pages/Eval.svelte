<script>
  let agents = $state([])
  let selectedAgent = $state('')
  let result = $state(null)
  let loading = $state(false)
  let error = $state(null)

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
</script>

<div class="eval-page">
  <div class="page-header">
    <h2>Evaluation</h2>
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
  </div>

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
      </p>
    </section>

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
                <div class="mismatch-row">
                  <span class="label">Expected</span>
                  <span class="mono expected">{fmt(m.expected)}</span>
                </div>
                <div class="mismatch-row">
                  <span class="label">Actual</span>
                  <span class="mono actual">{fmt(m.actual)}</span>
                </div>
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
    align-items: center;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }
  .page-header h2 { margin: 0; color: var(--text-strong); }

  .controls {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    margin-bottom: 1.5rem;
  }

  select {
    padding: 0.35rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: 4px;
    font-size: 0.875rem;
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
    font-size: 0.875rem;
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
  .accuracy-label { font-weight: 600; font-size: 0.9rem; color: var(--text-muted); }
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

  .meta { margin: 0; font-size: 0.82rem; color: var(--text-muted); }

  /* Tables */
  section { margin-bottom: 1.75rem; }

  h3 {
    margin: 0 0 0.75rem;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-strong);
  }
  .count { color: var(--text-muted); font-weight: 400; }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
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
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .badge {
    display: inline-block;
    padding: 0.1rem 0.45rem;
    border-radius: 10px;
    font-size: 0.78rem;
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
    font-size: 0.85rem;
    background: var(--bg-surface);
  }

  .mismatch-num {
    color: var(--text-muted);
    font-size: 0.78rem;
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
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-muted);
    min-width: 54px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .mono { font-family: monospace; font-size: 0.82rem; word-break: break-all; color: var(--text); }
  .expected { color: var(--pass); }
  .actual   { color: var(--fail); }

  .msg { padding: 0.5rem 0; }
  .error { color: var(--fail); }
  .muted { color: var(--text-muted); }
</style>
