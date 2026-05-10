<script>
  let agents = $state([])
  let loading = $state(true)
  let error = $state(null)
  let selected = $state(null)
  let detailLoading = $state(false)

  let grouped = $derived({
    catalog: agents.filter(a => a.source === 'catalog'),
    example: agents.filter(a => a.source === 'example'),
    integration_test: agents.filter(a => a.source === 'integration_test'),
  })

  $effect(() => {
    fetch('/api/catalog')
      .then(r => r.json())
      .then(data => { agents = data; loading = false })
      .catch(e => { error = e.message; loading = false })
  })

  async function openAgent(name) {
    detailLoading = true
    selected = null
    error = null
    try {
      const r = await fetch(`/api/catalog/${encodeURIComponent(name)}`)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      selected = await r.json()
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
      <h1>{selected.name}</h1>
      <div class="badges">
        {#if selected.agent_type}
          <span class="badge type">{selected.agent_type}</span>
        {/if}
        {#if selected.provider}
          <span class="badge provider">{selected.provider}</span>
        {/if}
        {#if selected.model}
          <span class="badge model">{selected.model}</span>
        {/if}
        {#if selected.version != null}
          <span class="badge version">v{selected.version}</span>
        {/if}
      </div>
    </div>

    {#if selected.output_schema}
      <section>
        <h2>Output Schema</h2>
        <p class="section-desc">The JSON schema for the structured output this agent returns, derived from its Pydantic model.</p>
        <pre class="code">{JSON.stringify(selected.output_schema, null, 2)}</pre>
      </section>
    {:else if selected.output_model}
      <section>
        <h2>Output Model</h2>
        <p class="section-desc">The Pydantic model class that defines the structured output for this agent.</p>
        <code class="inline-code">{selected.output_model}</code>
      </section>
    {/if}

    {#if selected.system_examples?.length}
      <section>
        <h2>Examples ({selected.system_examples.length})</h2>
        <p class="section-desc">Input/output pairs injected into the system prompt as few-shot examples — they guide the LLM toward the expected output format.</p>
        <div class="examples">
          {#each selected.system_examples.slice(0, 4) as ex}
            <div class="example">
              <div class="ex-row">
                <span class="ex-label">in</span>
                <code>{typeof ex.input === 'string' ? ex.input : JSON.stringify(ex.input)}</code>
              </div>
              <div class="ex-row">
                <span class="ex-label">out</span>
                <code>{JSON.stringify(ex.output)}</code>
              </div>
            </div>
          {/each}
          {#if selected.system_examples.length > 4}
            <p class="muted">+{selected.system_examples.length - 4} more in config</p>
          {/if}
        </div>
      </section>
    {/if}

    {#if selected.system_prompt}
      <section>
        <h2>System Prompt</h2>
        <p class="section-desc">The full system prompt sent to the LLM at the start of every request — it defines the agent's role, rules, and output format.</p>
        <pre class="code prompt">{selected.system_prompt}</pre>
      </section>
    {/if}

    <section>
      <h2>YAML Source</h2>
      <p class="section-desc">The raw YAML configuration file that defines this agent's model, provider, system prompt, and examples.</p>
      <pre class="code yaml-src">{selected.raw_yaml}</pre>
    </section>
  </div>

{:else}

  <div class="catalog">
    <div class="page-intro">
      <h1 class="page-title">Catalog</h1>
      <p class="intro-desc">Browse all agents registered on this instance. <strong>Catalog Agents</strong> are purpose-built for specific tasks. <strong>Framework Examples</strong> are reference implementations bundled with agents7 that demonstrate different agent types. <strong>Integration Tests</strong> are agents used to verify provider compatibility. Click any card to inspect its full configuration.</p>
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
              <button class="card" onclick={() => openAgent(agent.name)}>
                <div class="card-name">{agent.name}</div>
                <div class="card-meta">
                  {#if agent.agent_type}
                    <span class="badge type">{agent.agent_type}</span>
                  {/if}
                  {#if agent.model}
                    <span class="badge model">{agent.model}</span>
                  {/if}
                </div>
                <div class="card-footer">
                  {#if agent.provider}{agent.provider}{/if}
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
  .state-msg { color: var(--text-muted); font-size: 0.95rem; margin: 2rem 0; }
  .state-msg.error { color: var(--fail); }
  .muted { color: var(--text-muted); font-size: 0.88rem; margin: 0.25rem 0 0; }

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
    font-size: 0.875rem;
    line-height: 1.6;
    margin: 0;
    max-width: 700px;
  }

  /* Section descriptions in detail view */
  .section-desc {
    color: var(--text-muted);
    font-size: 0.82rem;
    line-height: 1.5;
    margin: 0 0 0.6rem;
  }

  /* Catalog */
  .catalog { max-width: 1200px; margin: 0 auto; }

  .detail { max-width: 900px; margin: 0 auto; }

  .section-heading {
    font-size: 0.72rem;
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
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 1rem;
  }
  .card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem 1rem 0.85rem;
    text-align: left;
    cursor: pointer;
    transition: box-shadow 0.15s, border-color 0.15s;
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
  }
  .card:hover { box-shadow: 0 2px 12px rgba(0,0,0,0.4); border-color: var(--accent); }
  .card-name { font-weight: 600; font-size: 0.97rem; color: var(--text-strong); }
  .card-meta { display: flex; gap: 0.35rem; flex-wrap: wrap; }
  .card-footer { font-size: 0.78rem; color: var(--text-muted); }

  /* Badges */
  .badge {
    display: inline-block;
    padding: 0.13rem 0.42rem;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .badge.type     { background: var(--info-bg);    color: var(--accent); }
  .badge.model    { background: var(--pass-bg);     color: var(--pass); }
  .badge.provider { background: var(--warn-bg);     color: var(--warn); }
  .badge.version  { background: var(--neutral-bg);  color: var(--neutral); }

  /* Detail */
  .back-btn {
    background: none;
    border: none;
    color: var(--accent);
    cursor: pointer;
    font-size: 0.88rem;
    padding: 0;
    margin-bottom: 1.25rem;
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
  }
  .back-btn:hover { text-decoration: underline; }

  .detail-header { margin-bottom: 1.75rem; }
  .detail-header h1 { font-size: 1.45rem; font-weight: 700; margin: 0 0 0.6rem; color: var(--text-strong); }
  .badges { display: flex; gap: 0.4rem; flex-wrap: wrap; }

  .detail section { margin-bottom: 1.75rem; }
  .detail section h2 {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--text-muted);
    margin: 0 0 0.55rem;
  }

  .code {
    background: var(--bg-raised);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.85rem 1rem;
    font-size: 0.8rem;
    line-height: 1.55;
    overflow-x: auto;
    white-space: pre;
    margin: 0;
    max-height: 300px;
    overflow-y: auto;
    font-family: ui-monospace, 'Cascadia Code', 'Fira Code', monospace;
    color: var(--text);
  }
  .code.prompt   { max-height: 220px; }
  .code.yaml-src { max-height: 340px; }

  .inline-code {
    background: var(--bg-raised);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.2rem 0.5rem;
    font-size: 0.85rem;
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
  .ex-row { display: flex; gap: 0.65rem; align-items: baseline; font-size: 0.83rem; }
  .ex-label {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    min-width: 22px;
  }
  .ex-row code { font-family: ui-monospace, monospace; color: var(--text); }
</style>
