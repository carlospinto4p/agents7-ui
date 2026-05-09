<script>
  let agents = $state([])
  let agentName = $state('')
  let jsonlText = $state('')
  let running = $state(false)
  let results = $state([])
  let loadError = $state(null)

  $effect(() => {
    fetch('/api/catalog')
      .then(r => r.json())
      .then(data => {
        agents = data
        if (data.length > 0) agentName = data[0].name
      })
      .catch(e => { loadError = e.message })
  })

  function parseLines() {
    return jsonlText
      .split('\n')
      .map(l => l.trim())
      .filter(l => l.length > 0)
      .map((l, i) => {
        try {
          return { idx: i, raw: l, parsed: JSON.parse(l), parseErr: null }
        } catch (e) {
          return { idx: i, raw: l, parsed: null, parseErr: e.message }
        }
      })
  }

  async function runBatch() {
    const lines = parseLines()
    if (lines.length === 0) return
    results = lines.map(l => ({
      idx: l.idx,
      raw: l.raw,
      status: l.parseErr ? 'parse-error' : 'pending',
      parseErr: l.parseErr,
      output: null,
      rawResponse: null,
      metrics: null,
      apiError: null,
    }))
    running = true

    for (let i = 0; i < results.length; i++) {
      if (results[i].status === 'parse-error') continue
      results[i].status = 'running'
      try {
        const r = await fetch(`/api/run/${encodeURIComponent(agentName)}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: results[i].raw,
        })
        if (!r.ok) {
          let detail = ''
          try { detail = (await r.json()).detail ?? '' } catch {}
          results[i].status = 'error'
          results[i].apiError = detail || `HTTP ${r.status}`
        } else {
          const data = await r.json()
          results[i].status = data.parse_error ? 'fail' : 'pass'
          results[i].output = data.output
          results[i].rawResponse = data.raw_response
          results[i].metrics = data.metrics
        }
      } catch (e) {
        results[i].status = 'error'
        results[i].apiError = e.message
      }
    }
    running = false
  }

  function handleFileUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => { jsonlText = ev.target.result ?? '' }
    reader.readAsText(file)
    e.target.value = ''
  }

  let passCount = $derived(results.filter(r => r.status === 'pass').length)
  let failCount = $derived(
    results.filter(r => ['fail', 'error', 'parse-error'].includes(r.status)).length
  )
  let doneCount = $derived(
    results.filter(r => !['pending', 'running'].includes(r.status)).length
  )

  function truncate(s, n = 60) {
    if (typeof s !== 'string') s = JSON.stringify(s)
    return s.length > n ? s.slice(0, n) + '…' : s
  }

  const STATUS_LABEL = {
    pass: '✓ pass',
    fail: '✗ fail',
    error: '✗ error',
    'parse-error': '⚠ json',
    running: '…',
    pending: '—',
  }
</script>

<div class="runner">
  <h1>Batch Runner</h1>

  {#if loadError}
    <p class="state-msg error">{loadError}</p>
  {:else}

    <div class="setup">
      <label class="field">
        <span class="label">Agent</span>
        <select bind:value={agentName} disabled={running}>
          {#each agents as a}
            <option value={a.name}>{a.name}</option>
          {/each}
        </select>
      </label>

      <div class="field">
        <span class="label">Input (JSONL — one object per line)</span>
        <textarea
          bind:value={jsonlText}
          rows="6"
          placeholder={'{"nick": "John"}\n{"nick": "Maria"}'}
          disabled={running}
          spellcheck="false"
        ></textarea>
        <div class="textarea-actions">
          <label class="upload-btn">
            Upload .jsonl
            <input type="file" accept=".jsonl,.json,.txt" onchange={handleFileUpload} disabled={running} />
          </label>
          <button
            class="clear-btn"
            onclick={() => { jsonlText = ''; results = [] }}
            disabled={running}
          >Clear</button>
        </div>
      </div>

      <button
        class="run-btn"
        onclick={runBatch}
        disabled={running || !agentName || !jsonlText.trim()}
      >
        {running ? `Running… (${doneCount}/${results.length})` : 'Run Batch'}
      </button>
    </div>

    {#if results.length > 0}
      <div class="results">
        <div class="results-header">
          <span class="results-title">Results — {doneCount}/{results.length}</span>
          <span class="pill pass">{passCount} passed</span>
          <span class="pill fail">{failCount} failed</span>
        </div>
        <table>
          <thead>
            <tr>
              <th class="col-num">#</th>
              <th class="col-input">Input</th>
              <th class="col-output">Output</th>
              <th class="col-status">Status</th>
              <th class="col-tokens">Tokens</th>
            </tr>
          </thead>
          <tbody>
            {#each results as row}
              <tr class="row-{row.status}">
                <td class="col-num">{row.idx + 1}</td>
                <td class="col-input mono">{truncate(row.raw, 55)}</td>
                <td class="col-output mono">
                  {#if row.output}
                    {truncate(JSON.stringify(row.output), 70)}
                  {:else if row.apiError}
                    <span class="err-text">{row.apiError}</span>
                  {:else if row.parseErr}
                    <span class="err-text">{row.parseErr}</span>
                  {:else}
                    —
                  {/if}
                </td>
                <td class="col-status">
                  <span class="status-badge s-{row.status}">
                    {STATUS_LABEL[row.status] ?? row.status}
                  </span>
                </td>
                <td class="col-tokens">{row.metrics?.tokens ?? '—'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

  {/if}
</div>

<style>
  .runner h1 { font-size: 1.3rem; margin: 0 0 1.5rem; font-weight: 600; color: #111; }
  .state-msg { color: #888; font-size: 0.95rem; }
  .state-msg.error { color: #cc3300; }

  .setup { display: flex; flex-direction: column; gap: 1rem; max-width: 700px; }

  .field { display: flex; flex-direction: column; gap: 0.35rem; }
  .label {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #555;
  }

  select {
    padding: 0.4rem 0.6rem;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    font-size: 0.92rem;
    background: #fff;
    width: fit-content;
    min-width: 200px;
  }
  select:disabled { background: #f5f5f5; color: #999; }

  textarea {
    padding: 0.6rem 0.75rem;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    font-size: 0.82rem;
    font-family: ui-monospace, 'Cascadia Code', monospace;
    resize: vertical;
    width: 100%;
    box-sizing: border-box;
    line-height: 1.55;
  }
  textarea:disabled { background: #f5f5f5; color: #999; }
  textarea::placeholder { color: #bbb; }

  .textarea-actions { display: flex; gap: 0.6rem; align-items: center; }

  .upload-btn {
    font-size: 0.82rem;
    color: #0066cc;
    cursor: pointer;
    padding: 0.25rem 0;
  }
  .upload-btn:hover { text-decoration: underline; }
  .upload-btn input { display: none; }

  .clear-btn {
    background: none;
    border: none;
    font-size: 0.82rem;
    color: #999;
    cursor: pointer;
    padding: 0.25rem 0;
  }
  .clear-btn:hover:not(:disabled) { color: #555; }
  .clear-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  .run-btn {
    padding: 0.5rem 1.2rem;
    background: #0066cc;
    color: #fff;
    border: none;
    border-radius: 6px;
    font-size: 0.92rem;
    font-weight: 600;
    cursor: pointer;
    width: fit-content;
    transition: background 0.15s;
  }
  .run-btn:hover:not(:disabled) { background: #0052a3; }
  .run-btn:disabled { background: #a0b8d4; cursor: not-allowed; }

  /* Results */
  .results { margin-top: 2rem; }
  .results-header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 0.75rem;
  }
  .results-title { font-size: 0.88rem; font-weight: 600; color: #333; }
  .pill {
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.13rem 0.5rem;
    border-radius: 999px;
  }
  .pill.pass { background: #f0fdf4; color: #166534; }
  .pill.fail { background: #fef2f2; color: #991b1b; }

  table { width: 100%; border-collapse: collapse; font-size: 0.83rem; }
  thead th {
    text-align: left;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #999;
    padding: 0.45rem 0.6rem;
    border-bottom: 1px solid #e4e7eb;
  }
  tbody tr { border-bottom: 1px solid #f0f0f0; }
  tbody tr:hover { background: #fafafa; }
  tbody td { padding: 0.45rem 0.6rem; vertical-align: top; color: #333; }

  .col-num    { width: 36px; text-align: right; color: #aaa; }
  .col-input  { width: 200px; }
  .col-output { }
  .col-status { width: 90px; white-space: nowrap; }
  .col-tokens { width: 70px; text-align: right; color: #888; }

  .mono { font-family: ui-monospace, 'Cascadia Code', monospace; font-size: 0.79rem; }
  .err-text { color: #cc3300; }

  .status-badge {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.13rem 0.42rem;
    border-radius: 4px;
  }
  .s-pass        { background: #f0fdf4; color: #166534; }
  .s-fail        { background: #fef2f2; color: #991b1b; }
  .s-error       { background: #fef2f2; color: #991b1b; }
  .s-parse-error { background: #fff7ed; color: #9a3412; }
  .s-running     { background: #eff6ff; color: #1d4ed8; }
  .s-pending     { background: #f1f5f9; color: #64748b; }
</style>
