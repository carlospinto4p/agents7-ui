<script>
  import JsonViewer from '../components/JsonViewer.svelte';
  import ChatPanel from '../components/ChatPanel.svelte';
  import { CHATTER_TYPES } from '../constants.js';

  let agents       = $state([])
  let loading      = $state(true)
  let error        = $state(null)
  let selected     = $state(null)
  let detailLoading = $state(false)

  // ── Collapse state (persists while component is mounted) ──
  let open = $state({
    runner: true, schema: true, examples: true,
    prompt: false, yaml: false,
  })

  // ── Inline runner ──────────────────────────────────────────
  let runnerValues  = $state({})
  let runnerText    = $state('')
  let runnerRunning  = $state(false)
  let runnerResult   = $state(null)
  let runnerError    = $state(null)
  let elapsedRunner  = $state(0)
  let runnerDuration = $state(null)
  let stepsOpen      = $state([])

  let grouped = $derived(
    agents.reduce(
      (acc, a) => {
        if (a.source in acc) acc[a.source].push(a)
        return acc
      },
      { catalog: [], example: [], integration_test: [] },
    )
  )

  let catalogChat = $state(null)

  // Chatter-family agents run through the stateful chat API, not the
  // one-shot /api/run runner — so the detail page embeds a chat panel
  // instead of a JSON input.
  let isChatterAgent = $derived(
    !!selected && CHATTER_TYPES.has(selected.agent_type)
  )

  let runnerExInput = $derived(
    selected?.system_examples?.[0]?.input ?? null
  )

  // Per-field inputs when example input is a plain object
  let runnerFields = $derived(
    runnerExInput != null &&
    typeof runnerExInput === 'object' &&
    !Array.isArray(runnerExInput)
      ? Object.entries(runnerExInput).map(([k, v]) => ({
          name: k,
          placeholder:
            typeof v === 'object' ? JSON.stringify(v) : String(v),
        }))
      : []
  )

  // Single text input when example input is a plain string
  let runnerIsText = $derived(
    runnerFields.length === 0 && typeof runnerExInput === 'string'
  )

  let runnerSubmittable = $derived(
    !runnerRunning &&
    !!selected &&
    (
      (runnerFields.length > 0 && runnerFields.every(f => (runnerValues[f.name] ?? '').trim() !== '')) ||
      (runnerIsText && runnerText.trim() !== '')
    )
  )

  $effect(() => {
    if (!runnerRunning) return
    runnerDuration = null
    elapsedRunner = 0
    const id = setInterval(() => { elapsedRunner++ }, 1000)
    return () => { clearInterval(id); runnerDuration = elapsedRunner }
  })

  let runnerMetaLine = $derived.by(() => {
    const parts = []
    if (runnerDuration != null) parts.push(`${runnerDuration}s`)
    if (runnerResult?.metrics?.tokens) parts.push(`${runnerResult.metrics.tokens} tok`)
    const modelLabel = selected?.step_engines?.length
      ? selected.step_engines.map(s => s.model).filter(Boolean).join(', ')
      : selected?.model
    if (modelLabel) parts.push(modelLabel)
    return parts.join(' · ')
  })

  $effect(() => {
    fetch('/api/catalog')
      .then(r => r.json())
      .then(data => { agents = data; loading = false })
      .catch(e => { error = e.message; loading = false })
  })

  async function openAgent(name) {
    detailLoading  = true
    selected       = null
    error          = null
    runnerValues   = {}
    runnerText     = ''
    runnerResult   = null
    runnerError    = null
    runnerDuration = null
    try {
      const r = await fetch(`/api/catalog/${encodeURIComponent(name)}`)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      selected = await r.json()
      const ex = selected?.system_examples?.[0]?.input
      if (ex && typeof ex === 'object' && !Array.isArray(ex)) {
        const defaults = {}
        for (const [k, v] of Object.entries(ex)) {
          defaults[k] = typeof v === 'object' ? JSON.stringify(v) : String(v)
        }
        runnerValues = defaults
      } else if (typeof ex === 'string') {
        runnerText = ex
      }
    } catch (e) {
      error = e.message
    } finally {
      detailLoading = false
    }
  }

  function back() {
    selected = null
    error = null
  }

  function toggle(key) { open[key] = !open[key] }

  async function runAgent() {
    if (!selected) return
    runnerRunning = true
    runnerResult  = null
    runnerError   = null

    let body
    if (runnerFields.length > 0) {
      body = {}
      for (const f of runnerFields) {
        const raw = runnerValues[f.name] ?? ''
        try { body[f.name] = JSON.parse(raw) }
        catch { body[f.name] = raw }
      }
    } else if (runnerIsText) {
      // API uses body.get("input_data", body) — wrap string inputs
      body = { input_data: runnerText }
    } else {
      try { body = JSON.parse(runnerText) }
      catch { body = runnerText }
    }

    try {
      const r = await fetch(
        `/api/run/${encodeURIComponent(selected.name)}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }
      )
      if (!r.ok) {
        let detail = ''
        try { detail = (await r.json()).detail ?? '' } catch {}
        runnerError = detail || `HTTP ${r.status}`
      } else {
        runnerResult = await r.json()
        stepsOpen = (runnerResult.steps ?? []).map(() => true)
      }
    } catch (e) {
      runnerError = e.message
    }
    runnerRunning = false
  }

  function outputEntries(obj) {
    if (!obj || typeof obj !== 'object') return []
    return Object.entries(obj)
  }
</script>

{#if loading}
  <p class="state-msg">Loading catalog…</p>
{:else if detailLoading}
  <p class="state-msg">Loading…</p>
{:else if error && !selected}
  <p class="state-msg error">{error}</p>
{:else if selected}

  <div class="detail">
    <button class="back-btn" onclick={back}>← Catalog</button>

    <div class="detail-header">
      <h1>{selected.display_name ?? selected.name}</h1>
      <div class="badges">
        {#if selected.agent_type}
          <span class="badge type">{selected.agent_type}</span>
        {/if}
        {#if selected.step_engines?.length}
          {#each [...new Set(selected.step_engines.map(s => s.provider).filter(Boolean))] as p}
            <span class="badge provider">{p}</span>
          {/each}
          {#each [...new Set(selected.step_engines.map(s => s.model).filter(Boolean))] as m}
            <span class="badge model">{m}</span>
          {/each}
        {:else}
          {#if selected.provider}
            <span class="badge provider">{selected.provider}</span>
          {/if}
          {#if selected.model}
            <span class="badge model">{selected.model}</span>
          {/if}
        {/if}
        {#if selected.version != null}
          <span class="badge version">v{selected.version}</span>
        {/if}
      </div>
      {#if selected.step_engines?.length}
        <div class="detail-step-engines">
          {#each selected.step_engines as s, i}
            {#if i > 0}<span class="step-arrow">→</span>{/if}
            <span class="step-engine">{s.name}{s.provider || s.model ? ` (${[s.provider, s.model].filter(Boolean).join(' / ')})` : ''}</span>
          {/each}
        </div>
      {:else if selected.pipeline_steps?.length}
        <div class="detail-steps">{selected.pipeline_steps.join(' → ')}</div>
      {/if}
    </div>

    <!-- Runner -->
    <section>
      <button class="sec-hdr" onclick={() => toggle('runner')}>
        <h2>Runner</h2>
        <span class="chevron" class:closed={!open.runner}>▾</span>
      </button>
      {#if open.runner}
        <div class="runner-body">
          {#if isChatterAgent}
            <p class="section-desc">
              Conversational agent with memory. Send it a message
              below, or open the full
              <a
                class="chatter-link"
                href={`#/chatter/${encodeURIComponent(selected.name)}`}
              >Chatter page →</a>
            </p>
            <div class="inline-chat">
              <ChatPanel bind:this={catalogChat} agentName={selected.name} />
            </div>
            <button
              class="reset-conv-btn"
              onclick={() => catalogChat?.restart()}
            >Reset conversation</button>
          {:else}
            <p class="section-desc">
              {runnerFields.length > 0 || runnerIsText
                ? 'Prefilled from a sample input — edit the values and Run.'
                : "Enter a JSON object matching this agent's input."}
            </p>
            {#if runnerFields.length > 0}
              <div class="runner-fields">
                {#each runnerFields as f}
                  <label class="runner-field">
                    <span class="field-label">{f.name}</span>
                    <input
                      type="text"
                      placeholder={f.placeholder}
                      bind:value={runnerValues[f.name]}
                      disabled={runnerRunning}
                      spellcheck="false"
                    />
                  </label>
                {/each}
              </div>
            {:else if runnerIsText}
              <label class="runner-field">
                <span class="field-label">Input</span>
                <input
                  type="text"
                  placeholder={runnerExInput ?? 'Enter input…'}
                  bind:value={runnerText}
                  disabled={runnerRunning}
                  spellcheck="false"
                />
              </label>
            {:else}
              <label class="runner-field">
                <span class="field-label">JSON Input</span>
                <textarea
                  rows="3"
                  placeholder={'{ "field": "value" }'}
                  bind:value={runnerText}
                  disabled={runnerRunning}
                  spellcheck="false"
                ></textarea>
              </label>
            {/if}

          <button
            class="run-btn"
            onclick={runAgent}
            disabled={!runnerSubmittable}
          >Run</button>

          {#if runnerRunning}
            <div class="loading-bar-wrap">
              <div class="loading-bar-track"><div class="loading-bar-fill"></div></div>
              <span class="running-hint">Running… {elapsedRunner}s</span>
            </div>
          {/if}

          {#if runnerError}
            <p class="runner-error">{runnerError}</p>
          {/if}

          {#if runnerResult}
            <div class="output-card">
              <div class="output-card-hdr">
                <span class="output-label">Output</span>
                {#if runnerResult.parse_error}
                  <span class="status-badge s-fail">parse error</span>
                {:else}
                  <span class="status-badge s-pass">✓ pass</span>
                {/if}
                {#if runnerMetaLine}
                  <span class="token-count">{runnerMetaLine}</span>
                {/if}
              </div>
              {#if runnerResult.parse_error}
                <pre class="raw-response">{runnerResult.raw_response}</pre>
              {:else if runnerResult.output}
                <table class="output-table">
                  <tbody>
                    {#each outputEntries(runnerResult.output) as [k, v]}
                      <tr>
                        <td class="out-key">{k}</td>
                        <td class="out-val">
                          {typeof v === 'object'
                            ? JSON.stringify(v)
                            : String(v)}
                        </td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              {/if}
            </div>

          {#if runnerResult.steps?.length > 0}
            <div class="steps-section">
              <span class="steps-label">Steps</span>
              {#each runnerResult.steps as step, i}
                <div class="step-card">
                  <button class="step-header" onclick={() => { stepsOpen[i] = !stepsOpen[i] }}>
                    <span class="step-num">{i + 1}</span>
                    <span class="step-name">{step.name}</span>
                    {#if selected.step_engines?.[i]?.provider}
                      <span class="badge provider">{selected.step_engines[i].provider}</span>
                    {/if}
                    {#if selected.step_engines?.[i]?.model}
                      <span class="badge model">{selected.step_engines[i].model}</span>
                    {/if}
                    {#if step.metrics?.tokens}
                      <span class="step-meta">{step.metrics.tokens} tok · {step.metrics.total_duration?.toFixed(1)}s</span>
                    {/if}
                    <span class="chevron" class:closed={!stepsOpen[i]}>▾</span>
                  </button>
                  {#if stepsOpen[i]}
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
                        <p class="muted">No output (parse error)</p>
                      {/if}
                    </div>
                  </div>
                  {/if}
                </div>
              {/each}
            </div>
          {/if}
          {/if}
          {/if}
        </div>
      {/if}
    </section>

    <!-- Output Schema / Model -->
    {#if selected.output_schema}
      <section>
        <button class="sec-hdr" onclick={() => toggle('schema')}>
          <h2>Output Schema</h2>
          <span class="chevron" class:closed={!open.schema}>▾</span>
        </button>
        {#if open.schema}
          <p class="section-desc">
            Derived from the agent's Pydantic output model.
          </p>
          <JsonViewer value={selected.output_schema} />
        {/if}
      </section>
    {:else if selected.output_model}
      <section>
        <button class="sec-hdr" onclick={() => toggle('schema')}>
          <h2>Output Model</h2>
          <span class="chevron" class:closed={!open.schema}>▾</span>
        </button>
        {#if open.schema}
          <p class="section-desc">
            The Pydantic model class that defines the structured output
            for this agent.
          </p>
          <code class="inline-code">{selected.output_model}</code>
        {/if}
      </section>
    {/if}

    <!-- Examples -->
    {#if selected.system_examples?.length}
      <section>
        <button class="sec-hdr" onclick={() => toggle('examples')}>
          <h2>Examples ({selected.system_examples.length})</h2>
          <span class="chevron" class:closed={!open.examples}>▾</span>
        </button>
        {#if open.examples}
          <p class="section-desc">
            Few-shot pairs injected into the system prompt to guide
            output format.
          </p>
          <div class="examples">
            {#each selected.system_examples.slice(0, 4) as ex}
              <div class="example">
                <div class="ex-row">
                  <span class="ex-label">in</span>
                  <code>{typeof ex.input === 'string'
                    ? ex.input
                    : JSON.stringify(ex.input)}</code>
                </div>
                <div class="ex-row">
                  <span class="ex-label">out</span>
                  <code>{ex.output != null ? JSON.stringify(ex.output) : '—'}</code>
                </div>
              </div>
            {/each}
            {#if selected.system_examples.length > 4}
              <p class="muted">
                +{selected.system_examples.length - 4} more in config
              </p>
            {/if}
          </div>
        {/if}
      </section>
    {/if}

    <!-- System Prompt -->
    {#if selected.system_prompt}
      <section>
        <button class="sec-hdr" onclick={() => toggle('prompt')}>
          <h2>System Prompt</h2>
          <span class="chevron" class:closed={!open.prompt}>▾</span>
        </button>
        {#if open.prompt}
          <p class="section-desc">
            Sent to the LLM at the start of every request.
          </p>
          <pre class="code prompt">{selected.system_prompt}</pre>
        {/if}
      </section>
    {/if}

    <!-- YAML Source -->
    <section>
      <button class="sec-hdr" onclick={() => toggle('yaml')}>
        <h2>YAML Source</h2>
        <span class="chevron" class:closed={!open.yaml}>▾</span>
      </button>
      {#if open.yaml}
        <p class="section-desc">
          The source configuration for this agent.
        </p>
        <pre class="code yaml-src">{selected.raw_yaml}</pre>
      {/if}
    </section>
  </div>

{:else}

  <div class="catalog">
    <div class="page-intro">
      <h1 class="page-title">Catalog</h1>
      <p class="intro-desc"><strong>Catalog agents</strong> are purpose-built for specific tasks. <strong>Framework examples</strong> are reference implementations bundled with agents7. <strong>Integration tests</strong> verify provider compatibility.</p>
    </div>
    {#if agents.length === 0}
      <p class="muted">No agents found in catalog.</p>
    {:else}
      {#each [
        { key: 'catalog', label: 'Catalog Agents' },
        { key: 'example', label: 'Framework Examples' },
        { key: 'integration_test', label: 'Framework Integration Tests' },
      ] as section}
        {#if grouped[section.key].length > 0}
          <h2 class="section-heading">{section.label}</h2>
          <div class="grid">
            {#each grouped[section.key] as agent}
              {@const cardModels = agent.step_engines?.length
                ? [...new Set(agent.step_engines.map(s => s.model).filter(Boolean))]
                : (agent.model ? [agent.model] : [])}
              {@const cardProvider = agent.step_engines?.length
                ? [...new Set(agent.step_engines.map(s => s.provider).filter(Boolean))].join(', ')
                : (agent.provider ?? '')}
              <button class="card" onclick={() => openAgent(agent.name)}>
                <div class="card-name">{agent.display_name ?? agent.name}</div>
                <div class="card-meta">
                  {#if agent.agent_type}
                    <span class="badge type">{agent.agent_type}</span>
                  {/if}
                  {#each cardModels as model}
                    <span class="badge model">{model}</span>
                  {/each}
                </div>
                {#if agent.pipeline_steps?.length}
                  <div class="card-steps">{agent.pipeline_steps.join(' → ')}</div>
                {/if}
                <div class="card-footer">
                  {#if cardProvider}{cardProvider}{/if}
                  {#if agent.version != null} · v{agent.version}{/if}
                </div>
              </button>
            {/each}
          </div>
        {/if}
      {/each}
    {/if}
  </div>

{/if}

<style>
  .state-msg { color: var(--text-muted); font-size: 1.0625rem; margin: 2rem 0; }
  .state-msg.error { color: var(--fail); }
  .muted { color: var(--text-muted); font-size: 1.0625rem; margin: 0.25rem 0 0; }

  /* Page intro */
  .page-intro { margin-bottom: 1.75rem; }
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
    max-width: 700px;
  }

  .section-desc {
    color: var(--text-muted);
    font-size: 1.0625rem;
    line-height: 1.5;
    margin: 0 0 0.6rem;
  }

  /* Catalog list */
  .catalog { max-width: 1200px; margin: 0 auto; }

  /* Detail */
  .detail { max-width: 900px; margin: 0 auto; }

  .section-heading {
    font-size: 1.0625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    margin: 1.75rem 0 0.75rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid var(--border);
  }
  .section-heading:first-child { margin-top: 0; }

  .grid {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
  }
  .card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem 1rem 0.85rem;
    text-align: left;
    cursor: pointer;
    transition: box-shadow 0.15s, border-color 0.15s, transform 0.15s;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    /* Grow to fill the row, but a long title widens its own card
       (min-width defaults to content, so the nowrap title sets the
       floor) instead of wrapping. */
    flex: 1 1 200px;
    max-width: 360px;
  }
  .card:hover {
    box-shadow: 0 4px 16px rgba(0,0,0,0.4);
    border-color: var(--accent);
    transform: translateY(-2px);
  }
  .card-name {
    font-weight: 600;
    font-size: 1.0625rem;
    color: var(--text-strong);
    line-height: 1.35;
    white-space: nowrap;
  }
  .card-meta { display: flex; gap: 0.4rem; flex-wrap: wrap; min-width: 0; }
  .card-steps { font-size: 1.0625rem; color: var(--text-muted); font-style: italic; }
  .card-footer { font-size: 1.0625rem; color: var(--text-muted); }

  /* Badges */
  .badge {
    display: inline-flex;
    align-items: center;
    max-width: 100%;
    padding: 0.1rem 0.5rem;
    border-radius: 999px;
    font-size: 0.9rem;
    font-weight: 500;
    line-height: 1.45;
    letter-spacing: 0.01em;
    /* Long model names wrap instead of overflowing the card. */
    overflow-wrap: anywhere;
    word-break: break-word;
  }
  .badge.type     { background: var(--info-bg);    color: var(--accent); }
  .badge.model    {
    background: var(--pass-bg);
    color: var(--pass);
    font-family: ui-monospace, 'Cascadia Code', monospace;
  }
  .badge.provider { background: var(--warn-bg);     color: var(--warn); }
  .badge.version  { background: var(--neutral-bg);  color: var(--neutral); }

  /* Back button */
  .back-btn {
    background: none;
    border: none;
    color: var(--accent);
    cursor: pointer;
    font-size: 1.0625rem;
    padding: 0;
    margin-bottom: 1.25rem;
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
  }
  .back-btn:hover { text-decoration: underline; }

  .detail-header { margin-bottom: 1.75rem; }
  .detail-header h1 {
    font-size: 1.45rem;
    font-weight: 700;
    margin: 0 0 0.6rem;
    color: var(--text-strong);
  }
  .badges { display: flex; gap: 0.4rem; flex-wrap: wrap; }
  .detail-steps { font-size: 1.0625rem; color: var(--text-muted); font-style: italic; margin-top: 0.5rem; }
  .detail-step-engines { font-size: 1.0625rem; color: var(--text-muted); margin-top: 0.5rem; display: flex; flex-wrap: wrap; align-items: center; gap: 0.25rem; }
  .step-arrow { color: var(--text-muted); opacity: 0.5; }
  .step-engine { font-style: italic; }

  /* Section layout */
  .detail section { margin-bottom: 1.75rem; }

  /* Collapsible section header */
  .sec-hdr {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: none;
    border: none;
    border-bottom: 1px solid var(--border);
    padding: 0 0 0.45rem;
    margin: 0 0 0.65rem;
    cursor: pointer;
    text-align: left;
  }
  .sec-hdr:hover h2 { color: var(--text); }

  .detail section .sec-hdr h2 {
    font-size: 1.0625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--text-muted);
    margin: 0;
    transition: color 0.12s;
  }

  .chevron {
    font-size: 1.0625rem;
    color: var(--text-muted);
    line-height: 1;
    transition: transform 0.18s;
  }
  .chevron.closed { transform: rotate(-90deg); }

  /* Collapsed section: tighten bottom margin */
  .detail section:has(.sec-hdr):not(:has(.runner-body)):not(:has(.section-desc)) {
    margin-bottom: 0.75rem;
  }

  /* Runner */
  .runner-body {
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
  }
  .runner-fields {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .runner-field {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }
  .field-label {
    font-size: 1.0625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
  }
  .runner-body input[type="text"] {
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
  .runner-body input[type="text"]:disabled { opacity: 0.4; }
  .runner-body input[type="text"]::placeholder { color: var(--text-muted); }
  .runner-body textarea {
    padding: 0.55rem 0.7rem;
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
  .runner-body textarea:disabled { opacity: 0.4; }
  .runner-body textarea::placeholder { color: var(--text-muted); }

  .run-btn {
    padding: 0.45rem 1.1rem;
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
  .run-btn:disabled {
    background: rgba(76, 158, 255, 0.3);
    cursor: not-allowed;
  }

  .runner-error {
    color: var(--fail);
    font-size: 1.0625rem;
    margin: 0;
  }

  /* Inline chat (chatter-family agents) */
  .inline-chat { height: 460px; }
  .chatter-link {
    color: var(--accent);
    text-decoration: none;
    font-weight: 600;
  }
  .chatter-link:hover { text-decoration: underline; }
  .reset-conv-btn {
    align-self: flex-start;
    padding: 0.35rem 0.85rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--bg-surface);
    color: var(--text-muted);
    font-size: 1.0625rem;
    cursor: pointer;
  }
  .reset-conv-btn:hover {
    background: var(--bg-raised);
    color: var(--text);
  }

  /* Output card */
  .output-card {
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }
  .output-card-hdr {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.85rem;
    background: var(--bg-raised);
    border-bottom: 1px solid var(--border);
  }
  .output-label {
    font-size: 1.0625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
  }
  .token-count {
    margin-left: auto;
    font-size: 1.0625rem;
    color: var(--text-muted);
  }

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
  .status-badge {
    display: inline-block;
    font-size: 1.0625rem;
    font-weight: 600;
    padding: 0.12rem 0.42rem;
    border-radius: 4px;
  }
  .s-pass { background: var(--pass-bg); color: var(--pass); }
  .s-fail { background: var(--fail-bg); color: var(--fail); }

  /* Existing code block styles */
  .code {
    background: var(--bg-raised);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.85rem 1rem;
    font-size: 1.0625rem;
    line-height: 1.55;
    overflow-x: auto;
    overflow-y: auto;
    white-space: pre;
    margin: 0;
    max-height: 300px;
    font-family: ui-monospace, 'Cascadia Code', 'Fira Code', monospace;
    color: var(--text);
    scrollbar-width: thin;
    scrollbar-color: var(--border) transparent;
  }
  .code::-webkit-scrollbar          { width: 5px; height: 5px; }
  .code::-webkit-scrollbar-track    { background: transparent; }
  .code::-webkit-scrollbar-corner   { background: transparent; }
  .code::-webkit-scrollbar-thumb    { background: var(--border); border-radius: 3px; }
  .code::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

  .code.prompt   { max-height: 220px; }
  .code.yaml-src { max-height: 340px; }

  .inline-code {
    background: var(--bg-raised);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.2rem 0.5rem;
    font-size: 1.0625rem;
    font-family: ui-monospace, monospace;
    color: var(--text);
  }

  /* Examples */
  .examples { display: flex; flex-direction: column; gap: 0.55rem; }
  .example {
    background: var(--bg-raised);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.55rem 0.85rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .ex-row {
    display: flex;
    gap: 0.65rem;
    align-items: baseline;
    font-size: 1.0625rem;
  }
  .ex-label {
    font-size: 1.0625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    min-width: 22px;
  }
  .ex-row code { font-family: ui-monospace, monospace; color: var(--text); }

  /* Pipeline steps breakdown */
  .steps-section {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
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
  .step-header:hover { background: var(--bg-raised); filter: brightness(1.05); }
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
