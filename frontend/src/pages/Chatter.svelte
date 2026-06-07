<script>
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

  // Allow deep links from the catalog (#/chatter/<name>) to
  // preselect a specific agent.
  function agentFromHash() {
    const parts = window.location.hash.replace('#/', '').split('/')
    return parts[0] === 'chatter' && parts[1]
      ? decodeURIComponent(parts[1])
      : ''
  }

  $effect(() => {
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
            <option value={a.name}>{a.name}</option>
          {/each}
        </select>
      {/if}
    </label>

    <button
      class="reset-btn"
      onclick={() => chatPanel?.restart()}
      disabled={!agentName}
    >
      Reset
    </button>
  </div>

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
    </div>
  {/if}

  {#if agentName}
    <div class="panel-wrap">
      <ChatPanel bind:this={chatPanel} {agentName} />
    </div>
  {:else}
    <div class="transcript-placeholder">
      <p class="empty-msg">Select an agent to start chatting.</p>
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
