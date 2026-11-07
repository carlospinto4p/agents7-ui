<script>
  import { history } from '../stores/history.js'
  import { isChatter, isToolAgent } from '../constants.js'
  import {
    fmtCost,
    cacheLabel,
    retryLabel,
    stepMetaLine,
    copyText,
    downloadJson,
  } from '../lib/format.js'

  // ── Shared state ─────────────────────────────────────────
  let agents     = $state([])
  let agentName  = $state('')
  let loadError  = $state(null)
  let tab        = $state('single')
  let historyOpen = $state(false)

  // Chatter-family agents are stateful and run through /api/chat
  // (the Chatter page), not the one-shot /api/run this page uses.
  // Excluding them keeps the Runner from landing on a conversational
  // agent that has no input schema and a permanently-disabled Run.
  let runnableAgents = $derived(agents.filter(a => !isChatter(a.agent_type)))

  // Summary (incl. description) of the currently selected agent,
  // looked up from the already-loaded catalog list.
  let selectedSummary = $derived(
    agents.find(a => a.name === agentName) ?? null
  )

  $effect(() => {
    fetch('/api/catalog')
      .then(r => r.json())
      .then(data => {
        agents = data
        const runnable = data.filter(a => !isChatter(a.agent_type))
        if (runnable.length > 0) agentName = runnable[0].name
      })
      .catch(e => { loadError = e.message })
  })

  // ── Single runner ─────────────────────────────────────────
  let agentDetail   = $state(null)
  let fieldValues   = $state({})
  let singleRunning   = $state(false)
  let singleResult    = $state(null)
  let singleError     = $state(null)
  let elapsedSingle   = $state(0)
  let singleDuration  = $state(null)
  let singleStepsOpen = $state([])

  // Key under which the single free-text input is stored in
  // `fieldValues` when the agent takes a bare string rather than a
  // dict of named fields.
  const TEXT_KEY = '__text__'

  let inputExample = $derived(agentDetail?.system_examples?.[0]?.input ?? null)

  let isTool = $derived(isToolAgent(selectedSummary?.agent_type))

  // Agents accept either a single free-text string (labelers,
  // classifiers, extractors) or a set of named fields (dict input).
  // Detecting which prevents spreading a string into one box per
  // character via `Object.entries`.
  //
  // A tool agent answers a user message, so it takes free text even
  // without a `system_examples` entry to infer the shape from —
  // otherwise it would fall through to 'none' and never be runnable.
  let inputMode = $derived(
    typeof inputExample === 'string'
      ? 'text'
      : inputExample && typeof inputExample === 'object' &&
          !Array.isArray(inputExample)
        ? 'fields'
        : isTool
          ? 'text'
          : 'none'
  )

  let inputFields = $derived(
    inputMode === 'fields'
      ? Object.entries(inputExample).map(([k, v]) => ({
          name: k,
          placeholder: typeof v === 'object' ? JSON.stringify(v) : String(v),
        }))
      : []
  )

  $effect(() => {
    if (!agentName) return
    singleResult   = null
    singleError    = null
    singleDuration = null
    fieldValues    = {}
    fetch(`/api/catalog/${encodeURIComponent(agentName)}`)
      .then(r => r.json())
      .then(data => {
        agentDetail = data
        const ex = data?.system_examples?.[0]?.input
        const defaults = {}
        if (typeof ex === 'string') {
          defaults[TEXT_KEY] = ex
        } else if (ex && typeof ex === 'object' && !Array.isArray(ex)) {
          for (const [k, v] of Object.entries(ex)) {
            defaults[k] = typeof v === 'object' ? JSON.stringify(v) : String(v)
          }
        }
        fieldValues = defaults
      })
      .catch(() => { agentDetail = null })
  })

  async function runSingle() {
    if (!agentName) return
    singleRunning = true
    singleResult  = null
    singleError   = null

    let body
    if (inputMode === 'text') {
      // Free-text agents expect the raw string as `input_data`; do
      // not JSON-parse it (a numeric-looking string stays a string).
      body = { input_data: fieldValues[TEXT_KEY] ?? '' }
    } else {
      body = {}
      for (const f of inputFields) {
        const raw = fieldValues[f.name] ?? ''
        try { body[f.name] = JSON.parse(raw) } catch { body[f.name] = raw }
      }
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
        singleStepsOpen = (data.steps ?? []).map(() => true)
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
    !singleRunning && !!agentName && (
      inputMode === 'text'
        ? (fieldValues[TEXT_KEY] ?? '').trim() !== ''
        : inputFields.length > 0 &&
          inputFields.every(f => (fieldValues[f.name] ?? '').trim() !== '')
    )
  )

  // Input object for display/download, mirroring the run payload
  // shape for either input mode.
  function currentSingleInput() {
    if (inputMode === 'text') {
      return { input_data: fieldValues[TEXT_KEY] ?? '' }
    }
    return Object.fromEntries(
      inputFields.map(f => [f.name, fieldValues[f.name] ?? '']),
    )
  }

  $effect(() => {
    if (!singleRunning) return
    singleDuration = null
    elapsedSingle = 0
    const id = setInterval(() => { elapsedSingle++ }, 1000)
    return () => { clearInterval(id); singleDuration = elapsedSingle }
  })

  let singleMetaLine = $derived.by(() => {
    const parts = []
    if (singleDuration != null) parts.push(`${singleDuration}s`)
    if (singleResult?.metrics?.tokens) parts.push(`${singleResult.metrics.tokens} tok`)
    const cost = fmtCost(singleResult?.metrics?.cost_cents)
    if (cost) parts.push(cost)
    const cached = cacheLabel(singleResult?.metrics)
    if (cached) parts.push(cached)
    // The duration above is this page's own stopwatch, which was
    // running through the retries too — so this says how much of
    // it went on attempts that failed.
    const retries = retryLabel(singleResult?.metrics)
    if (retries) parts.push(retries)
    if (agentDetail?.model) parts.push(agentDetail.model)
    return parts.join(' · ')
  })

  function outputEntries(obj) {
    if (!obj || typeof obj !== 'object') return []
    return Object.entries(obj)
  }

  // Pair each tool call with the result that answered it. The backend
  // reports the loop as a flat event list; within one iteration the
  // results follow that iteration's calls in the same order, so the
  // first still-unresolved call of an iteration owns the next result.
  let toolCallSteps = $derived.by(() => {
    const steps = singleResult?.tool_steps
    if (!steps) return []
    const calls = []
    const byIteration = new Map()
    for (const s of steps) {
      if (s.kind === 'tool_call') {
        const call = {
          name: s.name,
          iteration: s.iteration,
          arguments: s.arguments ?? {},
          result: null,
          error: null,
        }
        calls.push(call)
        if (!byIteration.has(s.iteration)) byIteration.set(s.iteration, [])
        byIteration.get(s.iteration).push(call)
      } else if (s.kind === 'tool_result') {
        const match = (byIteration.get(s.iteration) ?? []).find(
          c => c.result === null,
        )
        if (match) {
          match.result = s.result ?? ''
          // `error` is the flag, not the text: `result` already holds
          // the "Error: ..." message the model was handed, and a tool
          // may return text starting with "Error:" and have succeeded.
          match.error = s.error ?? null
        }
      }
    }
    return calls
  })

  let copiedSingle = $state(false)
  async function copySingleOutput() {
    const ok = await copyText(
      JSON.stringify(singleResult.output ?? singleResult.raw_response, null, 2),
    )
    if (ok) {
      copiedSingle = true
      setTimeout(() => { copiedSingle = false }, 1200)
    }
  }
  function downloadSingleOutput() {
    downloadJson(`${agentName || 'output'}.json`, {
      agent: agentName,
      input: currentSingleInput(),
      output: singleResult.output,
      metrics: singleResult.metrics,
    })
  }

  // ── Batch runner ──────────────────────────────────────────
  let jsonlText    = $state('')
  let running      = $state(false)
  let results      = $state([])
  let elapsedBatch = $state(0)
  let batchDuration = $state(null)

  $effect(() => {
    if (!running) return
    batchDuration = null
    elapsedBatch = 0
    const id = setInterval(() => { elapsedBatch++ }, 1000)
    return () => { clearInterval(id); batchDuration = elapsedBatch }
  })

  function parseLines() {
    const out = []
    let idx = 0
    for (const line of jsonlText.split('\n')) {
      const l = line.trim()
      if (!l) continue
      try {
        out.push({ idx: idx++, raw: l, parsed: JSON.parse(l), parseErr: null })
      } catch (e) {
        out.push({ idx: idx++, raw: l, parsed: null, parseErr: e.message })
      }
    }
    return out
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

  let { passCount, failCount, doneCount } = $derived.by(() => {
    let pass = 0, fail = 0, done = 0
    for (const r of results) {
      if (r.status === 'pass') pass++
      else if (r.status === 'fail' || r.status === 'error' || r.status === 'parse-error') fail++
      if (r.status !== 'pending' && r.status !== 'running') done++
    }
    return { passCount: pass, failCount: fail, doneCount: done }
  })

  function truncate(s, n = 60) {
    if (typeof s !== 'string') s = JSON.stringify(s)
    return s.length > n ? s.slice(0, n) + '…' : s
  }

  const STATUS_LABEL = {
    pass: '✓ pass', fail: '✗ fail', error: '✗ error',
    'parse-error': '⚠ json', running: '…', pending: '—',
  }

  function downloadBatch() {
    downloadJson(`${agentName || 'batch'}-results.json`,
      results.map(r => ({
        idx: r.idx,
        input: r.raw,
        status: r.status,
        output: r.output,
        error: r.apiError ?? r.parseErr ?? null,
        metrics: r.metrics,
      })),
    )
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
              {#each runnableAgents as a}
                <option value={a.name}>{a.display_name || a.name}</option>
              {/each}
            </select>
          </label>

          {#if selectedSummary?.agent_type}
            <div class="agent-type-row">
              <span class="badge type">{selectedSummary.agent_type}</span>
            </div>
          {/if}

          {#if selectedSummary?.description}
            <p class="agent-desc">{selectedSummary.description}</p>
          {/if}

          {#if inputMode === 'text'}
            <div class="single-form">
              <label class="field">
                <span class="label">Input text</span>
                <textarea
                  rows="3"
                  placeholder={inputExample ?? ''}
                  bind:value={fieldValues[TEXT_KEY]}
                  disabled={singleRunning}
                  spellcheck="false"
                ></textarea>
              </label>
            </div>
          {:else if inputFields.length > 0}
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
          >Run</button>

          {#if singleRunning}
            <div class="loading-bar-wrap">
              <div class="loading-bar-track"><div class="loading-bar-fill"></div></div>
              <span class="running-hint">Running… {elapsedSingle}s</span>
            </div>
          {/if}

          {#if singleError}
            <p class="state-msg error">{singleError}</p>
          {/if}

          {#if singleResult}
            <div class="output-card">
              <div class="output-card-header">
                <span class="output-label">{singleResult.tool_steps ? 'Answer' : 'Output'}</span>
                {#if singleResult.error}
                  <span class="status-badge s-fail">loop error</span>
                {:else if singleResult.parse_error}
                  <span class="status-badge s-fail">parse error</span>
                {:else}
                  <span class="status-badge s-pass">✓ pass</span>
                {/if}
                {#if singleMetaLine}
                  <span class="token-count">{singleMetaLine}</span>
                {/if}
                <div class="card-actions">
                  <button class="tool-btn" onclick={copySingleOutput}>
                    {copiedSingle ? '✓ Copied' : 'Copy'}
                  </button>
                  {#if !singleResult.parse_error && singleResult.output}
                    <button class="tool-btn" onclick={downloadSingleOutput}>
                      ⬇ JSON
                    </button>
                  {/if}
                </div>
              </div>

              {#if singleResult.tool_steps}
                {#if singleResult.error}
                  <p class="state-msg error">{singleResult.error}</p>
                {:else}
                  <p class="answer-text">{singleResult.answer}</p>
                {/if}
              {:else if singleResult.parse_error}
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

          {#if toolCallSteps.length > 0}
            <div class="steps-section" data-testid="tool-trajectory">
              <span class="steps-label">Trajectory <span class="steps-count">({toolCallSteps.length} {toolCallSteps.length === 1 ? 'call' : 'calls'})</span></span>
              {#each toolCallSteps as step, i}
                <div class="step-card tool-step" class:rejected={step.error != null}>
                  <div class="tool-step-header">
                    <span class="step-num">{i + 1}</span>
                    <span class="tool-name">{step.name}</span>
                    {#if step.error != null}
                      <span class="tool-rejected" data-testid="tool-rejected">rejected</span>
                    {/if}
                    <span class="tool-iteration">iteration {step.iteration + 1}</span>
                  </div>
                  <div class="tool-step-body">
                    <div class="tool-io">
                      <span class="io-label">Arguments</span>
                      {#if Object.keys(step.arguments ?? {}).length > 0}
                        <table class="output-table">
                          <tbody>
                            {#each outputEntries(step.arguments) as [k, v]}
                              <tr>
                                <td class="out-key">{k}</td>
                                <td class="out-val">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</td>
                              </tr>
                            {/each}
                          </tbody>
                        </table>
                      {:else}
                        <p class="state-msg">No arguments</p>
                      {/if}
                    </div>
                    <div class="tool-io">
                      <span class="io-label">{step.error != null ? 'Error' : 'Result'}</span>
                      {#if step.result != null}
                        <pre class="tool-result" class:rejected={step.error != null}>{step.result}</pre>
                      {:else}
                        <p class="state-msg">No result — the loop ended before this call returned.</p>
                      {/if}
                    </div>
                  </div>
                </div>
              {/each}
            </div>
          {/if}

          {#if singleResult.steps?.length > 0}
            <div class="steps-section">
              <span class="steps-label">Steps</span>
              {#each singleResult.steps as step, i}
                <div class="step-card">
                  <button class="step-header" onclick={() => { singleStepsOpen[i] = !singleStepsOpen[i] }}>
                    <span class="step-num">{i + 1}</span>
                    <span class="step-name">{step.name}</span>
                    {#if agentDetail?.step_engines?.[i]?.provider}
                      <span class="badge provider">{agentDetail.step_engines[i].provider}</span>
                    {/if}
                    {#if agentDetail?.step_engines?.[i]?.model}
                      <span class="badge model">{agentDetail.step_engines[i].model}</span>
                    {/if}
                    {#if step.metrics?.tokens}
                      <span class="step-meta">{stepMetaLine(step.metrics)}</span>
                    {/if}
                    <span class="chevron" class:closed={!singleStepsOpen[i]}>▾</span>
                  </button>
                  {#if singleStepsOpen[i]}
                  <div class="step-body">
                    <div class="step-io">
                      <span class="io-label">Input</span>
                      <table class="output-table">
                        <tbody>
                          {#each outputEntries(step.input) as [k, v]}
                            <tr>
                              <td class="out-key">{k}</td>
                              <td class="out-val">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</td>
                            </tr>
                          {/each}
                        </tbody>
                      </table>
                    </div>
                    <div class="step-io">
                      <span class="io-label">Output</span>
                      {#if step.output}
                        <table class="output-table">
                          <tbody>
                            {#each outputEntries(step.output) as [k, v]}
                              <tr>
                                <td class="out-key">{k}</td>
                                <td class="out-val">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</td>
                              </tr>
                            {/each}
                          </tbody>
                        </table>
                      {:else}
                        <p class="state-msg">No output (parse error)</p>
                      {/if}
                    </div>
                  </div>
                  {/if}
                </div>
              {/each}
            </div>
          {/if}
          {/if}
        </div>

      <!-- ── Batch tab ──────────────────────────────────── -->
      {:else}
        <div class="setup">
          <label class="field">
            <span class="label">Agent</span>
            <select bind:value={agentName} disabled={running}>
              {#each runnableAgents as a}
                <option value={a.name}>{a.display_name || a.name}</option>
              {/each}
            </select>
          </label>

          {#if selectedSummary?.agent_type}
            <div class="agent-type-row">
              <span class="badge type">{selectedSummary.agent_type}</span>
            </div>
          {/if}

          {#if selectedSummary?.description}
            <p class="agent-desc">{selectedSummary.description}</p>
          {/if}

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
          >Run Batch</button>

          {#if running}
            <div class="loading-bar-wrap">
              <div class="loading-bar-track"><div class="loading-bar-fill"></div></div>
              <span class="running-hint">Running… {doneCount}/{results.length} rows · {elapsedBatch}s</span>
            </div>
          {/if}
        </div>

        {#if results.length > 0}
          <div class="results">
            <div class="results-header">
              <span class="results-title">Results — {doneCount}/{results.length}{batchDuration != null ? ` · ${batchDuration}s` : ''}</span>
              <span class="pill pass">{passCount} passed</span>
              <span class="pill fail">{failCount} failed</span>
              {#if doneCount > 0}
                <button class="tool-btn results-dl" onclick={downloadBatch}>
                  ⬇ JSON
                </button>
              {/if}
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

  .page-intro { margin-bottom: 1.5rem; }
  .page-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-strong);
    margin: 0 0 0.4rem;
  }
  .intro-desc {
    color: var(--text-muted);
    font-size: 1.0625rem;
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
    font-size: 1.0625rem;
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
    font-size: 1.0625rem;
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
    font-size: 1.0625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
  }

  .agent-type-row { margin-top: -0.4rem; }

  .agent-desc {
    margin: -0.4rem 0 0;
    font-size: 1.0625rem;
    line-height: 1.5;
    color: var(--text-muted);
  }

  select {
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 1.0625rem;
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
    font-size: 1.0625rem;
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
    font-size: 1.0625rem;
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
    font-size: 1.0625rem;
    color: var(--accent);
    cursor: pointer;
    padding: 0.25rem 0;
  }
  .upload-btn:hover { text-decoration: underline; }
  .upload-btn input { display: none; }

  .clear-btn {
    background: none;
    border: none;
    font-size: 1.0625rem;
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
    font-size: 1.0625rem;
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
    font-size: 1.0625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin-right: 0.25rem;
  }
  .token-count { margin-left: auto; font-size: 1.0625rem; color: var(--text-muted); }

  .card-actions { display: flex; gap: 0.4rem; margin-left: auto; }
  .tool-btn {
    background: none;
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text-muted);
    font-size: 1.0625rem;
    padding: 0.15rem 0.55rem;
    cursor: pointer;
    white-space: nowrap;
  }
  .tool-btn:hover { background: var(--bg-surface); color: var(--text); }
  .results-dl { margin-left: auto; }

  /* Loading bar */
  .loading-bar-wrap { display: flex; flex-direction: column; gap: 0.3rem; }
  .loading-bar-track {
    height: 3px;
    background: var(--border);
    border-radius: 2px;
    overflow: hidden;
    position: relative;
  }
  .loading-bar-fill {
    position: absolute;
    top: 0; left: 0; height: 100%; width: 35%;
    background: var(--accent);
    border-radius: 2px;
    animation: loading-slide 1.2s ease-in-out infinite;
  }
  @keyframes loading-slide {
    0%   { left: -35%; }
    100% { left: 110%; }
  }
  .running-hint { font-size: 1.0625rem; color: var(--text-muted); }

  .raw-response {
    margin: 0;
    padding: 0.75rem 0.85rem;
    font-size: 1.0625rem;
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
    font-size: 1.0625rem;
    font-weight: 600;
    color: var(--text-muted);
    width: 140px;
    white-space: nowrap;
    vertical-align: top;
    background: var(--bg-surface);
  }
  .out-val {
    padding: 0.45rem 0.85rem;
    font-size: 1.0625rem;
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
  .results-title { font-size: 1.0625rem; font-weight: 600; color: var(--text-strong); }
  .pill {
    font-size: 1.0625rem;
    font-weight: 600;
    padding: 0.13rem 0.5rem;
    border-radius: 999px;
  }
  .pill.pass { background: var(--pass-bg); color: var(--pass); }
  .pill.fail { background: var(--fail-bg); color: var(--fail); }

  table { width: 100%; border-collapse: collapse; font-size: 1.0625rem; }
  thead th {
    text-align: left;
    font-size: 1.0625rem;
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

  .mono { font-family: ui-monospace, 'Cascadia Code', monospace; font-size: 1.0625rem; }
  .err-text { color: var(--fail); }

  .status-badge {
    display: inline-block;
    font-size: 1.0625rem;
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
    font-size: 1.0625rem;
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
    font-size: 1.0625rem;
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
    font-size: 1.0625rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .entry-ts {
    font-size: 1.0625rem;
    color: var(--text-muted);
  }

  .entry-badge {
    font-size: 1.0625rem;
    font-weight: 600;
    padding: 0.1rem 0.38rem;
    border-radius: 4px;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .badge-pass  { background: var(--pass-bg); color: var(--pass); }
  .badge-fail  { background: var(--fail-bg); color: var(--fail); }
  .badge-error { background: var(--warn-bg); color: var(--warn); }

  .state-msg { color: var(--text-muted); font-size: 1.0625rem; }
  .state-msg.error { color: var(--fail); }

  /* Badges (reused from Catalog inside step headers) */
  .badge {
    display: inline-block;
    padding: 0.1rem 0.38rem;
    border-radius: 4px;
    font-size: 1.0625rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .badge.model    { background: var(--pass-bg);  color: var(--pass); }
  .badge.provider { background: var(--warn-bg);  color: var(--warn); }
  .badge.type     { background: var(--info-bg);  color: var(--accent); }

  /* Tool-agent answer and trajectory */
  .answer-text {
    margin: 0;
    padding: 0.75rem 0.9rem;
    font-size: 1.0625rem;
    line-height: 1.6;
    color: var(--text);
    white-space: pre-wrap;
  }

  .steps-count {
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
  }

  .tool-step-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.45rem 0.85rem;
    background: var(--bg-raised);
    border-bottom: 1px solid var(--border);
  }
  .tool-name {
    font-family: monospace;
    font-size: 1.0625rem;
    font-weight: 600;
    color: var(--text-strong);
  }
  .tool-iteration {
    margin-left: auto;
    font-size: 1.0625rem;
    color: var(--text-muted);
  }

  .tool-step-body {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    padding: 0.7rem 0.85rem;
  }
  .tool-io { display: flex; flex-direction: column; gap: 0.3rem; }

  .tool-result {
    margin: 0;
    padding: 0.5rem 0.65rem;
    background: var(--bg-raised);
    border-radius: 6px;
    font-family: monospace;
    font-size: 1.0625rem;
    white-space: pre-wrap;
    word-break: break-word;
    color: var(--text);
    overflow-x: auto;
  }

  /* A call the tool threw out. It reached the tool and got no
     answer back, so it must not read like an ordinary result. */
  .tool-step.rejected { border-color: var(--fail); }
  .tool-rejected {
    padding: 0.1rem 0.5rem;
    border-radius: 999px;
    background: var(--fail-bg);
    color: var(--fail);
    font-size: 0.9375rem;
    font-weight: 500;
  }
  .tool-result.rejected {
    background: var(--fail-bg);
    color: var(--fail);
  }

  /* Pipeline steps breakdown */
  .steps-section {
    margin-top: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    max-width: 700px;
  }
  .steps-label {
    font-size: 1.0625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
  }
  .step-card {
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }
  .step-header {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.45rem 0.85rem;
    background: var(--bg-raised);
    border: none;
    border-bottom: 1px solid var(--border);
    text-align: left;
    cursor: pointer;
  }
  .step-header:hover { filter: brightness(1.05); }
  .step-num {
    font-size: 1.0625rem;
    font-weight: 700;
    background: var(--accent);
    color: #fff;
    border-radius: 50%;
    width: 18px;
    height: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .step-name {
    font-size: 1.0625rem;
    font-weight: 600;
    color: var(--text-strong);
  }
  .step-meta {
    margin-left: auto;
    font-size: 1.0625rem;
    color: var(--text-muted);
  }
  .step-body { display: flex; flex-direction: column; }
  .step-io {
    padding: 0.5rem 0.85rem;
    border-bottom: 1px solid var(--border);
  }
  .step-io:last-child { border-bottom: none; }
  .io-label {
    display: block;
    font-size: 1.0625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-muted);
    margin-bottom: 0.35rem;
  }
</style>
