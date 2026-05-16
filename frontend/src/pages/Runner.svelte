<script>
  import { history } from '../stores/history.js'

  // ── Shared state ─────────────────────────────────────────
  let agents     = $state([])
  let agentName  = $state('')
  let loadError  = $state(null)
  let tab        = $state('single')
  let historyOpen = $state(false)

  $effect(() => {
    fetch('/api/catalog')
      .then(r => r.json())
      .then(data => {
        agents = data
        if (data.length > 0) agentName = data[0].name
      })
      .catch(e => { loadError = e.message })
  })

  // ── Single runner ─────────────────────────────────────────
  let agentDetail   = $state(null)
  let fieldValues   = $state({})
  let singleRunning = $state(false)
  let singleResult  = $state(null)
  let singleError   = $state(null)

  let inputFields = $derived(
    agentDetail?.system_examples?.[0]?.input
      ? Object.entries(agentDetail.system_examples[0].input).map(([k, v]) => ({
          name: k,
          placeholder: typeof v === 'object' ? JSON.stringify(v) : String(v),
        }))
      : []
  )

  $effect(() => {
    if (!agentName) return
    singleResult = null
    singleError  = null
    fieldValues  = {}
    fetch(`/api/catalog/${encodeURIComponent(agentName)}`)
      .then(r => r.json())
      .then(data => { agentDetail = data })
      .catch(() => { agentDetail = null })
  })

  async function runSingle() {
    if (!agentName) return
    singleRunning = true
    singleResult  = null
    singleError   = null

    const body = {}
    for (const f of inputFields) {
      const raw = fieldValues[f.name] ?? ''
      try { body[f.name] = JSON.parse(raw) } catch { body[f.name] = raw }
    }

    try {
      const r = await fetch(`/api/run/${encodeURIComponent(agentName)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!r.ok) {
        let detail = ''
        try { detail = (await r.json()).detail ?? '' } catch {}
        singleError = detail || `HTTP ${r.status}`
        history.add({
          id: Date.now(), ts: new Date().toISOString(),
          agent: agentName, mode: 'single',
          status: 'error', input: body, output: null, metrics: null,
        })
      } else {
        const data = await r.json()
        singleResult = data
        history.add({
          id: Date.now(), ts: new Date().toISOString(),
          agent: agentName, mode: 'single',
          status: data.parse_error ? 'fail' : 'pass',
          input: body, output: data.output, metrics: data.metrics,
        })
      }
    } catch (e) {
      singleError = e.message
      history.add({
        id: Date.now(), ts: new Date().toISOString(),
        agent: agentName, mode: 'single',
        status: 'error', input: body, output: null, metrics: null,
      })
    }
    singleRunning = false
  }

  let singleSubmittable = $derived(
    !singleRunning && !!agentName && inputFields.length > 0
  )

  function outputEntries(obj) {
    if (!obj || typeof obj !== 'object') return []
    return Object.entries(obj)
  }

  // ── Batch runner ──────────────────────────────────────────
  let jsonlText  = $state('')
  let running    = $state(false)
  let results    = $state([])

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

    async function runOne(i) {
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

    const CONCURRENCY = 4
    const indices = results
      .map((_, i) => i)
      .filter(i => results[i].status !== 'parse-error')
    for (let i = 0; i < indices.length; i += CONCURRENCY) {
      await Promise.all(indices.slice(i, i + CONCURRENCY).map(j => runOne(j)))
    }

    let pass = 0, fail = 0
    for (const r of results) {
      if (r.status === 'pass') pass++
      else if (['fail', 'error', 'parse-error'].includes(r.status)) fail++
    }
    history.add({
      id: Date.now(), ts: new Date().toISOString(),
      agent: agentName, mode: 'batch',
      status: fail === 0 ? 'pass' : pass === 0 ? 'fail' : 'mixed',
      rowCount: results.length, passCount: pass, failCount: fail,
    })
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
  let failCount = $derived(results.filter(r => ['fail', 'error', 'parse-error'].includes(r.status)).length)
  let doneCount = $derived(results.filter(r => !['pending', 'running'].includes(r.status)).length)

  function truncate(s, n = 60) {
    if (typeof s !== 'string') s = JSON.stringify(s)
    return s.length > n ? s.slice(0, n) + '…' : s
  }

  const STATUS_LABEL = {
    pass: '✓ pass', fail: '✗ fail', error: '✗ error',
    'parse-error': '⚠ json', running: '…', pending: '—',
  }

  // ── History helpers ───────────────────────────────────────
  function fmtTs(iso) {
    const d = new Date(iso)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  function historyStatus(entry) {
    if (entry.mode === 'batch') {
      if (entry.status === 'mixed')
        return `${entry.passCount}✓ ${entry.failCount}✗`
      return entry.status === 'pass' ? 'all pass' : 'all fail'
    }
    return entry.status
  }
</script>

<div class="page">
  <div class="runner" class:shifted={historyOpen}>

    {#if loadError}
      <p class="state-msg error">{loadError}</p>
    {:else}

      <div class="page-intro">
        <h1 class="page-title">Runner</h1>
        <p class="intro-desc"><strong>Single</strong> — type inputs and get the structured output immediately. <strong>Batch</strong> — paste or upload JSONL to process up to 4 rows in parallel.</p>
      </div>

      <div class="runner-header">
        <div class="tabs">
          <button
            class="tab-btn"
            class:active={tab === 'single'}
            onclick={() => tab = 'single'}
          >Single</button>
          <button
            class="tab-btn"
            class:active={tab === 'batch'}
            onclick={() => tab = 'batch'}
          >Batch</button>
        </div>
        <button
          class="history-toggle"
          class:open={historyOpen}
          onclick={() => historyOpen = !historyOpen}
        >History ({$history.length})</button>
      </div>

      <!-- ── Single tab ─────────────────────────────────── -->
      {#if tab === 'single'}
        <div class="setup">
          <label class="field">
            <span class="label">Agent</span>
            <select bind:value={agentName} disabled={singleRunning}>
              {#each agents as a}
                <option value={a.name}>{a.name}</option>
              {/each}
            </select>
          </label>

          {#if inputFields.length > 0}
            <div class="single-form">
              {#each inputFields as f}
                <label class="field">
                  <span class="label">{f.name}</span>
                  <input
                    type="text"
                    placeholder={f.placeholder}
                    bind:value={fieldValues[f.name]}
                    disabled={singleRunning}
                    spellcheck="false"
                  />
                </label>
              {/each}
            </div>
          {:else if agentDetail}
            <p class="state-msg">No input schema found for this agent.</p>
          {:else if agentName}
            <p class="state-msg">Loading…</p>
          {/if}

          <button
            class="run-btn"
            onclick={runSingle}
            disabled={!singleSubmittable}
          >
            {singleRunning ? 'Running…' : 'Run'}
          </button>

          {#if singleError}
            <p class="state-msg error">{singleError}</p>
          {/if}

          {#if singleResult}
            <div class="output-card">
              <div class="output-card-header">
                <span class="output-label">Output</span>
                {#if singleResult.parse_error}
                  <span class="status-badge s-fail">parse error</span>
                {:else}
                  <span class="status-badge s-pass">✓ pass</span>
                {/if}
                {#if singleResult.metrics?.tokens}
                  <span class="token-count">{singleResult.metrics.tokens} tokens</span>
                {/if}
              </div>

              {#if singleResult.parse_error}
                <pre class="raw-response">{singleResult.raw_response}</pre>
              {:else if singleResult.output}
                <table class="output-table">
                  <tbody>
                    {#each outputEntries(singleResult.output) as [k, v]}
                      <tr>
                        <td class="out-key">{k}</td>
                        <td class="out-val">
                          {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                        </td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              {/if}
            </div>
          {/if}
        </div>

      <!-- ── Batch tab ──────────────────────────────────── -->
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
                <input
                  type="file"
                  accept=".jsonl,.json,.txt"
                  onchange={handleFileUpload}
                  disabled={running}
                />
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

    {/if}
  </div>

  <!-- ── History sidebar ────────────────────────────────── -->
  {#if historyOpen}
    <aside class="history-sidebar">
      <div class="sidebar-header">
        <span class="sidebar-title">History</span>
        {#if $history.length > 0}
          <button class="clear-btn" onclick={() => history.clear()}>Clear</button>
        {/if}
      </div>
      {#if $history.length === 0}
        <p class="state-msg">No runs yet.</p>
      {:else}
        <ul class="history-list">
          {#each $history as entry}
            <li class="history-entry">
              <div class="entry-top">
                <span class="entry-agent">{entry.agent}</span>
                <span class="entry-badge {entry.status === 'pass' || entry.status === 'all pass' ? 'badge-pass' : entry.status === 'error' ? 'badge-error' : 'badge-fail'}">
                  {historyStatus(entry)}
                </span>
              </div>
              <div class="entry-bottom">
                <span class="entry-mode">{entry.mode}</span>
                <span class="entry-ts">{fmtTs(entry.ts)}</span>
              </div>
            </li>
          {/each}
        </ul>
      {/if}
    </aside>
  {/if}
</div>

<style>
  .page {
    display: flex;
    gap: 0;
    height: 100%;
  }

  .page-intro { margin-bottom: 1.5rem; max-width: 700px; }
  .page-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-strong);
    margin: 0 0 0.4rem;
  }
  .intro-desc {
    color: var(--text-muted);
    font-size: 0.875rem;
    line-height: 1.6;
    margin: 0;
  }

  .runner {
    flex: 1;
    min-width: 0;
    transition: margin-right 0.2s;
  }

  .runner-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  /* Tabs */
  .tabs {
    display: flex;
    gap: 0;
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
  }
  .tab-btn {
    padding: 0.35rem 0.85rem;
    border: none;
    background: var(--bg-surface);
    font-size: 0.88rem;
    font-weight: 500;
    color: var(--text-muted);
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }
  .tab-btn + .tab-btn { border-left: 1px solid var(--border); }
  .tab-btn.active {
    background: var(--accent);
    color: #fff;
    font-weight: 600;
  }
  .tab-btn:not(.active):hover { background: var(--bg-raised); }

  /* History toggle */
  .history-toggle {
    margin-left: auto;
    padding: 0.35rem 0.85rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--bg-surface);
    font-size: 0.85rem;
    color: var(--text-muted);
    cursor: pointer;
    transition: background 0.12s, border-color 0.12s;
  }
  .history-toggle:hover { background: var(--bg-raised); }
  .history-toggle.open {
    background: var(--accent-dim);
    border-color: var(--accent);
    color: var(--accent);
    font-weight: 600;
  }

  /* Setup form */
  .setup { display: flex; flex-direction: column; gap: 1rem; max-width: 700px; }

  .field { display: flex; flex-direction: column; gap: 0.35rem; }
  .label {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
  }

  select {
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 0.92rem;
    background: var(--bg-surface);
    color: var(--text);
    width: fit-content;
    min-width: 200px;
  }
  select:disabled { opacity: 0.4; }

  input[type="text"] {
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 0.92rem;
    font-family: ui-monospace, 'Cascadia Code', monospace;
    width: 100%;
    box-sizing: border-box;
    background: var(--bg-surface);
    color: var(--text);
  }
  input[type="text"]:disabled { opacity: 0.4; }
  input[type="text"]::placeholder { color: var(--text-muted); }

  .single-form { display: flex; flex-direction: column; gap: 0.75rem; }

  textarea {
    padding: 0.6rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 0.82rem;
    font-family: ui-monospace, 'Cascadia Code', monospace;
    resize: vertical;
    width: 100%;
    box-sizing: border-box;
    line-height: 1.55;
    background: var(--bg-surface);
    color: var(--text);
  }
  textarea:disabled { opacity: 0.4; }
  textarea::placeholder { color: var(--text-muted); }

  .textarea-actions { display: flex; gap: 0.6rem; align-items: center; }

  .upload-btn {
    font-size: 0.82rem;
    color: var(--accent);
    cursor: pointer;
    padding: 0.25rem 0;
  }
  .upload-btn:hover { text-decoration: underline; }
  .upload-btn input { display: none; }

  .clear-btn {
    background: none;
    border: none;
    font-size: 0.82rem;
    color: var(--text-muted);
    cursor: pointer;
    padding: 0.25rem 0;
  }
  .clear-btn:hover:not(:disabled) { color: var(--text); }
  .clear-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  .run-btn {
    padding: 0.5rem 1.2rem;
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: 6px;
    font-size: 0.92rem;
    font-weight: 600;
    cursor: pointer;
    width: fit-content;
    transition: background 0.15s;
  }
  .run-btn:hover:not(:disabled) { background: #3a8ef0; }
  .run-btn:disabled { background: rgba(76, 158, 255, 0.3); cursor: not-allowed; }

  /* Output card */
  .output-card {
    margin-top: 0.5rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    max-width: 700px;
  }
  .output-card-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.55rem 0.85rem;
    background: var(--bg-raised);
    border-bottom: 1px solid var(--border);
  }
  .output-label {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin-right: 0.25rem;
  }
  .token-count { margin-left: auto; font-size: 0.78rem; color: var(--text-muted); }

  .raw-response {
    margin: 0;
    padding: 0.75rem 0.85rem;
    font-size: 0.82rem;
    font-family: ui-monospace, 'Cascadia Code', monospace;
    white-space: pre-wrap;
    word-break: break-all;
    color: var(--fail);
    background: var(--bg-surface);
  }

  .output-table { width: 100%; border-collapse: collapse; }
  .output-table tr { border-bottom: 1px solid var(--border); }
  .output-table tr:last-child { border-bottom: none; }
  .out-key {
    padding: 0.45rem 0.85rem;
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text-muted);
    width: 140px;
    white-space: nowrap;
    vertical-align: top;
    background: var(--bg-surface);
  }
  .out-val {
    padding: 0.45rem 0.85rem;
    font-size: 0.88rem;
    color: var(--text);
    font-family: ui-monospace, 'Cascadia Code', monospace;
    word-break: break-all;
    background: var(--bg-surface);
  }

  /* Batch results */
  .results { margin-top: 2rem; }
  .results-header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 0.75rem;
  }
  .results-title { font-size: 0.88rem; font-weight: 600; color: var(--text-strong); }
  .pill {
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.13rem 0.5rem;
    border-radius: 999px;
  }
  .pill.pass { background: var(--pass-bg); color: var(--pass); }
  .pill.fail { background: var(--fail-bg); color: var(--fail); }

  table { width: 100%; border-collapse: collapse; font-size: 0.83rem; }
  thead th {
    text-align: left;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted);
    padding: 0.45rem 0.6rem;
    border-bottom: 1px solid var(--border);
    background: var(--bg-raised);
  }
  tbody tr { border-bottom: 1px solid var(--border); }
  tbody tr:hover { background: var(--bg-raised); }
  tbody td { padding: 0.45rem 0.6rem; vertical-align: top; color: var(--text); }

  .col-num    { width: 36px; text-align: right; color: var(--text-muted); }
  .col-input  { width: 200px; }
  .col-status { width: 90px; white-space: nowrap; }
  .col-tokens { width: 70px; text-align: right; color: var(--text-muted); }

  .mono { font-family: ui-monospace, 'Cascadia Code', monospace; font-size: 0.79rem; }
  .err-text { color: var(--fail); }

  .status-badge {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.13rem 0.42rem;
    border-radius: 4px;
  }
  .s-pass        { background: var(--pass-bg);     color: var(--pass); }
  .s-fail        { background: var(--fail-bg);     color: var(--fail); }
  .s-error       { background: var(--fail-bg);     color: var(--fail); }
  .s-parse-error { background: var(--warn-bg);     color: var(--warn); }
  .s-running     { background: var(--info-bg);     color: var(--accent); }
  .s-pending     { background: var(--neutral-bg);  color: var(--neutral); }

  /* History sidebar */
  .history-sidebar {
    width: 240px;
    flex-shrink: 0;
    border-left: 1px solid var(--border);
    padding: 0 0 1rem;
    margin-left: 1.5rem;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .sidebar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 0.75rem 0.75rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 0.5rem;
  }
  .sidebar-title {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
  }

  .history-list {
    list-style: none;
    margin: 0;
    padding: 0;
    overflow-y: auto;
    flex: 1;
  }
  .history-entry {
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid var(--border);
    cursor: default;
  }
  .history-entry:hover { background: var(--bg-raised); }
  .entry-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.35rem;
    margin-bottom: 0.2rem;
  }
  .entry-agent {
    font-size: 0.83rem;
    font-weight: 600;
    color: var(--text-strong);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .entry-bottom {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .entry-mode {
    font-size: 0.72rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .entry-ts {
    font-size: 0.72rem;
    color: var(--text-muted);
  }

  .entry-badge {
    font-size: 0.68rem;
    font-weight: 600;
    padding: 0.1rem 0.38rem;
    border-radius: 4px;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .badge-pass  { background: var(--pass-bg); color: var(--pass); }
  .badge-fail  { background: var(--fail-bg); color: var(--fail); }
  .badge-error { background: var(--warn-bg); color: var(--warn); }

  .state-msg { color: var(--text-muted); font-size: 0.95rem; }
  .state-msg.error { color: var(--fail); }
</style>
