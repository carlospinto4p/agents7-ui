<script>
  import { onMount } from 'svelte'
  import ChatPanel from '../components/ChatPanel.svelte'
  import { CHATTER_TYPES } from '../constants.js'

  let allAgents = $state([])
  let agents    = $derived(allAgents.filter(a => CHATTER_TYPES.has(a.agent_type)))
  let agentName = $state('')
  let loadError = $state(null)
  let chatPanel = $state(null)

  let selectedAgent = $derived(
    allAgents.find(a => a.name === agentName) ?? null
  )

  // Engine override — chat with a different model/provider than the
  // one baked into the agent config. Empty provider = agent default.
  let providers      = $state([])   // [{ name, ready, detail, model? }]
  let ollamaModels   = $state([])   // installed Ollama model names
  let ovProvider     = $state('')
  let ovModel        = $state('')

  let providerInfo = $derived(
    providers.find(p => p.name === ovProvider) ?? null
  )
  // ollama picks from the installed list; API providers take a free
  // model name (openai_compat may read it from the environment).
  let modelIsList = $derived(ovProvider === 'ollama')
  // An override with no model can only work when the provider supplies
  // one itself (openai_compat, via the environment). Otherwise starting
  // would fail server-side with a 400, so block it here instead.
  let needsModel = $derived(
    !!ovProvider && !ovModel && !providerInfo?.model
  )

  // Reset to the agent's default engine whenever the agent changes,
  // so an override never silently carries across a different persona.
  $effect(() => {
    agentName
    ovProvider = ''
    ovModel = ''
  })

  // Seed a sensible model when a provider is chosen: the agent's own
  // model if Ollama has it, else the first installed model; API
  // providers start blank for the user to type.
  function onProviderChange() {
    if (ovProvider === 'ollama') {
      const names = ollamaModels.map(m => m.name)
      const agentModel = selectedAgent?.model
      ovModel = names.includes(agentModel) ? agentModel : names[0] || ''
    } else if (providerInfo?.model) {
      ovModel = providerInfo.model
    } else {
      ovModel = ''
    }
  }

  // Per-agent detail (persona / scene / system prompt) for the blurb.
  let detail  = $state(null)
  let persona = $derived(detail?.persona ?? null)
  let scene   = $derived(detail?.scene ?? null)
  let personaFacts = $derived.by(() => {
    if (!persona) return ''
    return [persona.occupation, persona.nationality]
      .filter(Boolean)
      .join(' · ')
  })

  // Fetch the selected agent's detail whenever the selection changes.
  $effect(() => {
    const name = agentName
    detail = null
    if (!name) return
    fetch(`/api/catalog/${encodeURIComponent(name)}`)
      .then(r => (r.ok ? r.json() : null))
      .then(d => { if (name === agentName) detail = d })
      .catch(() => {})
  })

  // Allow deep links from the catalog (#/chatter/<name>) to
  // preselect a specific agent.
  function agentFromHash() {
    const parts = window.location.hash.replace('#/', '').split('/')
    return parts[0] === 'chatter' && parts[1]
      ? decodeURIComponent(parts[1])
      : ''
  }

  // Load the agent list once on mount (preselect via deep link).
  // Not a reactive effect, so it never re-fires on state changes.
  onMount(() => {
    fetch('/api/catalog')
      .then(r => r.json())
      .then(data => {
        allAgents = data
        const wanted = agentFromHash()
        const match =
          wanted &&
          data.find(
            a => a.name === wanted && CHATTER_TYPES.has(a.agent_type),
          )
        const first = match || data.find(a => CHATTER_TYPES.has(a.agent_type))
        if (first) agentName = first.name
      })
      .catch(e => { loadError = e.message })

    // Engine-override options — failures are non-fatal; the override
    // controls simply stay empty and the agent default is used.
    fetch('/api/chat/providers')
      .then(r => (r.ok ? r.json() : { providers: [] }))
      .then(d => { providers = d.providers ?? [] })
      .catch(() => {})
    fetch('/api/engine/models')
      .then(r => (r.ok ? r.json() : { models: [] }))
      .then(d => { ollamaModels = d.models ?? [] })
      .catch(() => {})
  })
</script>

<div class="chatter">

  <div class="page-intro">
    <h1 class="page-title">Chatter</h1>
    <p class="intro-desc">Multi-turn conversations with memory. Enter to send, Shift+Enter for a newline. Reset starts a fresh session with the same agent.</p>
  </div>

  <div class="controls">
    <label class="field">
      <span class="label">Agent</span>
      {#if loadError}
        <span class="err">{loadError}</span>
      {:else if agents.length === 0}
        <span class="muted">No chatter agents in catalog</span>
      {:else}
        <select bind:value={agentName}>
          {#each agents as a}
            <option value={a.name}>{a.name} — {a.agent_type}</option>
          {/each}
        </select>
      {/if}
    </label>

    <label class="field">
      <span class="label">Provider</span>
      <select
        bind:value={ovProvider}
        onchange={onProviderChange}
        disabled={!agentName}
      >
        <option value="">Agent default</option>
        {#each providers as p}
          <option value={p.name} disabled={!p.ready}>
            {p.name}{p.ready ? '' : ` (${p.detail})`}
          </option>
        {/each}
      </select>
    </label>

    {#if ovProvider}
      <label class="field">
        <span class="label">Model</span>
        {#if modelIsList}
          <select bind:value={ovModel} disabled={!agentName}>
            {#if ollamaModels.length === 0}
              <option value="">No models installed</option>
            {/if}
            {#each ollamaModels as m}
              <option value={m.name}>{m.name}</option>
            {/each}
          </select>
        {:else}
          <input
            type="text"
            class="model-input"
            bind:value={ovModel}
            placeholder="model name"
            spellcheck="false"
            disabled={!agentName}
          />
        {/if}
      </label>
    {/if}

    <button
      class="reset-btn"
      onclick={() => chatPanel?.restart()}
      disabled={!agentName}
    >
      Reset
    </button>
  </div>

  {#if ovProvider && providerInfo && !providerInfo.ready}
    <p class="override-warn">
      {ovProvider} is not ready: {providerInfo.detail}. Starting a chat
      with it will fail until configured.
    </p>
  {:else if needsModel}
    <p class="override-warn">
      {#if modelIsList}
        No Ollama model to run {ovProvider} with — install one, or pick
        a different provider.
      {:else}
        Enter a model name to chat with {ovProvider}.
      {/if}
    </p>
  {/if}

  {#if selectedAgent}
    <div class="agent-meta">
      {#if selectedAgent.display_name && selectedAgent.display_name !== selectedAgent.name}
        <span class="agent-display-name">{selectedAgent.display_name}</span>
      {/if}
      <div class="meta-badges">
        {#if selectedAgent.agent_type}
          <span class="badge type">{selectedAgent.agent_type}</span>
        {/if}
        {#if selectedAgent.provider}
          <span class="badge provider">{selectedAgent.provider}</span>
        {/if}
        {#if selectedAgent.model}
          <span class="badge model">{selectedAgent.model}</span>
        {/if}
        {#if selectedAgent.version != null}
          <span class="badge version">v{selectedAgent.version}</span>
        {/if}
      </div>

      {#if selectedAgent.description}
        <p class="agent-description">{selectedAgent.description}</p>
      {/if}

      {#if persona?.backstory || detail?.system_prompt || scene}
        <div class="persona-blurb">
          {#if personaFacts}
            <p class="persona-facts">{personaFacts}</p>
          {/if}
          {#if persona?.personality?.length}
            <div class="trait-tags">
              {#each persona.personality as trait}
                <span class="trait">{trait}</span>
              {/each}
            </div>
          {/if}
          {#if persona?.backstory}
            <p class="blurb-text">{persona.backstory}</p>
          {:else if detail?.system_prompt}
            <p class="blurb-text">{detail.system_prompt}</p>
          {/if}
          {#if scene}
            <p class="blurb-text">
              <span class="blurb-label">Scene</span>{scene.setting}{scene.situation
                ? ' ' + scene.situation
                : ''}
            </p>
          {/if}
        </div>
      {/if}
    </div>
  {/if}

  {#if agentName && !needsModel}
    <div class="panel-wrap">
      <ChatPanel
        bind:this={chatPanel}
        {agentName}
        provider={ovProvider}
        model={ovModel}
      />
    </div>
  {:else}
    <div class="transcript-placeholder">
      <p class="empty-msg">
        {#if !agentName}
          Select an agent to start chatting.
        {:else}
          Choose a model for {ovProvider} to start chatting.
        {/if}
      </p>
    </div>
  {/if}

</div>

<style>
  .page-intro { flex-shrink: 0; margin-bottom: 0.25rem; }
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

  .chatter {
    display: flex;
    flex-direction: column;
    height: calc(100vh - 4rem);
    max-width: 780px;
    margin: 0 auto;
    gap: 0.75rem;
  }

  .controls {
    display: flex;
    align-items: flex-end;
    gap: 1rem;
    flex-shrink: 0;
    flex-wrap: wrap;
  }

  .field { display: flex; flex-direction: column; gap: 0.3rem; }
  .label {
    font-size: 1.0625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
  }

  select {
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 1.0625rem;
    background: var(--bg-surface);
    color: var(--text);
    min-width: 220px;
  }
  select:disabled { opacity: 0.4; }

  .model-input {
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 1.0625rem;
    font-family: ui-monospace, 'Cascadia Code', monospace;
    background: var(--bg-surface);
    color: var(--text);
    min-width: 200px;
  }
  .model-input:disabled { opacity: 0.4; }
  .model-input:focus { outline: none; border-color: var(--accent); }

  .override-warn {
    flex-shrink: 0;
    margin: 0;
    font-size: 1.0625rem;
    line-height: 1.5;
    color: var(--warn);
  }

  .reset-btn {
    padding: 0.4rem 0.9rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--bg-surface);
    color: var(--text-muted);
    font-size: 1.0625rem;
    cursor: pointer;
  }
  .reset-btn:hover:not(:disabled) {
    background: var(--bg-raised);
    color: var(--text);
  }
  .reset-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  .err   { color: var(--fail); font-size: 1.0625rem; }
  .muted { color: var(--text-muted); font-size: 1.0625rem; }

  /* Selected-agent summary */
  .agent-meta {
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .agent-display-name {
    font-size: 1.0625rem;
    font-weight: 600;
    color: var(--text-strong);
  }
  .meta-badges { display: flex; gap: 0.4rem; flex-wrap: wrap; min-width: 0; }
  .agent-description {
    margin: 0;
    max-width: 640px;
    font-size: 1.0625rem;
    line-height: 1.5;
    color: var(--text-muted);
  }
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
    overflow-wrap: anywhere;
    word-break: break-word;
  }
  .badge.type     { background: var(--info-bg);   color: var(--accent); }
  .badge.model    {
    background: var(--pass-bg);
    color: var(--pass);
    font-family: ui-monospace, 'Cascadia Code', monospace;
  }
  .badge.provider { background: var(--warn-bg);    color: var(--warn); }
  .badge.version  { background: var(--neutral-bg); color: var(--neutral); }

  /* Persona / scene blurb */
  .persona-blurb {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    max-height: 9rem;
    overflow-y: auto;
    margin-top: 0.1rem;
  }
  .persona-facts {
    font-size: 1.0625rem;
    font-weight: 600;
    color: var(--text);
    margin: 0;
    text-transform: capitalize;
  }
  .trait-tags { display: flex; gap: 0.35rem; flex-wrap: wrap; }
  .trait {
    font-size: 0.9rem;
    padding: 0.05rem 0.45rem;
    border-radius: 999px;
    background: var(--bg-raised);
    border: 1px solid var(--border);
    color: var(--text-muted);
  }
  .blurb-text {
    font-size: 1.0625rem;
    line-height: 1.5;
    color: var(--text-muted);
    margin: 0;
  }
  .blurb-label {
    font-size: 1.0625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin-right: 0.4rem;
  }

  .panel-wrap { flex: 1; min-height: 0; display: flex; }

  .transcript-placeholder {
    flex: 1;
    display: flex;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg-surface);
  }
  .empty-msg {
    color: var(--text-muted);
    font-size: 1.0625rem;
    text-align: center;
    margin: auto;
  }
</style>
