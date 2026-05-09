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
    const slots = new Array(CONCURRENCY).fill(Promise.resolve())
    let slot = 0
    const all = results
      .map((_, i) => i)
      .filter(i => results[i].status !== 'parse-error')
      .map(i => {
        const p = slots[slot].then(() => runOne(i))
        slots[slot] = p
        slot = (slot + 1) % CONCURRENCY
        return p
      })
    await Promise.allSettled(all)

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

  const _counts = $derived.by(() => {
    let pass = 0, fail = 0, done = 0
    for (const r of results) {
      if (r.status === 'pass') pass++
      if (['fail', 'error', 'parse-error'].includes(r.status)) fail++
      if (!['pending', 'running'].includes(r.status)) done++
    }
    return { pass, fail, done }
  })
  let passCount = $derived(_counts.pass)
  let failCount = $derived(_counts.fail)
  let doneCount = $derived(_counts.done)

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
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    overflow: hidden;
  }
  .tab-btn {
    padding: 0.35rem 0.85rem;
    border: none;
    background: #fff;
    font-size: 0.88rem;
    font-weight: 500;
    color: #666;
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }
  .tab-btn + .tab-btn { border-left: 1px solid #d0d0d0; }
  .tab-btn.active {
    background: #0066cc;
    color: #fff;
    font-weight: 600;
  }
  .tab-btn:not(.active):hover { background: #f5f5f5; }

  /* History toggle */
  .history-toggle {
    margin-left: auto;
    padding: 0.35rem 0.85rem;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    background: #fff;
    font-size: 0.85rem;
    color: #555;
    cursor: pointer;
    transition: background 0.12s, border-color 0.12s;
  }
  .history-toggle:hover { background: #f5f5f5; }
  .history-toggle.open {
    background: #f0f4ff;
    border-color: #a8bfef;
    color: #1d4ed8;
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

  input[type="text"] {
    padding: 0.4rem 0.6rem;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    font-size: 0.92rem;
    font-family: ui-monospace, 'Cascadia Code', monospace;
    width: 100%;
    box-sizing: border-box;
  }
  input[type="text"]:disabled { background: #f5f5f5; color: #999; }
  input[type="text"]::placeholder { color: #bbb; }

  .single-form { display: flex; flex-direction: column; gap: 0.75rem; }

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

  /* Output card */
  .output-card {
    margin-top: 0.5rem;
    border: 1px solid #e4e7eb;
    border-radius: 8px;
    overflow: hidden;
    max-width: 700px;
  }
  .output-card-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.55rem 0.85rem;
    background: #f9fafb;
    border-bottom: 1px solid #e4e7eb;
  }
  .output-label {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #555;
    margin-right: 0.25rem;
  }
  .token-count { margin-left: auto; font-size: 0.78rem; color: #999; }

  .raw-response {
    margin: 0;
    padding: 0.75rem 0.85rem;
    font-size: 0.82rem;
    font-family: ui-monospace, 'Cascadia Code', monospace;
    white-space: pre-wrap;
    word-break: break-all;
    color: #cc3300;
  }

  .output-table { width: 100%; border-collapse: collapse; }
  .output-table tr { border-bottom: 1px solid #f0f0f0; }
  .output-table tr:last-child { border-bottom: none; }
  .out-key {
    padding: 0.45rem 0.85rem;
    font-size: 0.82rem;
    font-weight: 600;
    color: #555;
    width: 140px;
    white-space: nowrap;
    vertical-align: top;
  }
  .out-val {
    padding: 0.45rem 0.85rem;
    font-size: 0.88rem;
    color: #111;
    font-family: ui-monospace, 'Cascadia Code', monospace;
    word-break: break-all;
  }

  /* Batch results */
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

  /* History sidebar */
  .history-sidebar {
    width: 240px;
    flex-shrink: 0;
    border-left: 1px solid #e4e7eb;
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
    border-bottom: 1px solid #f0f0f0;
    margin-bottom: 0.5rem;
  }
  .sidebar-title {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #555;
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
    border-bottom: 1px solid #f5f5f5;
    cursor: default;
  }
  .history-entry:hover { background: #fafafa; }
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
    color: #222;
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
    color: #aaa;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .entry-ts {
    font-size: 0.72rem;
    color: #bbb;
  }

  .entry-badge {
    font-size: 0.68rem;
    font-weight: 600;
    padding: 0.1rem 0.38rem;
    border-radius: 4px;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .badge-pass  { background: #f0fdf4; color: #166534; }
  .badge-fail  { background: #fef2f2; color: #991b1b; }
  .badge-error { background: #fff7ed; color: #9a3412; }

  .state-msg { color: #888; font-size: 0.95rem; }
  .state-msg.error { color: #cc3300; }
</style>
