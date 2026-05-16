<script>
  const CHATTER_TYPES = new Set([
    'chatter', 'personality_chatter', 'scene_chatter',
    'guarded_chatter', 'guarded_scene_chatter',
  ])

  let allAgents   = $state([])
  let agents      = $derived(allAgents.filter(a => CHATTER_TYPES.has(a.agent_type)))
  let agentName   = $state('')
  let sessionId   = $state(null)
  let messages    = $state([])   // [{role, text, tokens?}]
  let input       = $state('')
  let sending     = $state(false)
  let starting    = $state(false)
  let loadError   = $state(null)
  let chatError   = $state(null)

  $effect(() => {
    fetch('/api/catalog')
      .then(r => r.json())
      .then(data => {
        allAgents = data
        const first = data.find(a => CHATTER_TYPES.has(a.agent_type))
        if (first) {
          agentName = first.name
          startSession()
        }
      })
      .catch(e => { loadError = e.message })
  })

  async function startSession() {
    if (!agentName || starting) return
    starting = true
    chatError = null
    if (sessionId) {
      await fetch(`/api/chat/${sessionId}`, { method: 'DELETE' })
    }
    messages = []
    try {
      const r = await fetch(
        `/api/chat/start/${encodeURIComponent(agentName)}`,
        { method: 'POST' },
      )
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        chatError = d.detail || `HTTP ${r.status}`
      } else {
        const d = await r.json()
        sessionId = d.session_id
      }
    } catch (e) {
      chatError = e.message
    }
    starting = false
  }

  async function sendMessage() {
    if (!sessionId || !input.trim() || sending) return
    const text = input.trim()
    input = ''
    sending = true
    chatError = null
    messages = [...messages, { role: 'user', text }]

    try {
      const r = await fetch(`/api/chat/${sessionId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        chatError = d.detail || `HTTP ${r.status}`
      } else {
        const d = await r.json()
        messages = [
          ...messages,
          { role: 'assistant', text: d.response, tokens: d.metrics?.tokens },
        ]
      }
    } catch (e) {
      chatError = e.message
    }
    sending = false
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }
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
        <select
          bind:value={agentName}
          disabled={sending || starting}
          onchange={() => startSession()}
        >
          {#each agents as a}
            <option value={a.name}>{a.name}</option>
          {/each}
        </select>
      {/if}
    </label>

    <button
      class="reset-btn"
      onclick={startSession}
      disabled={!agentName || starting || sending}
    >
      {starting ? 'Starting…' : 'Reset'}
    </button>
  </div>

  {#if chatError}
    <p class="err-msg">{chatError}</p>
  {/if}

  <div class="transcript" id="transcript">
    {#if !sessionId && !starting}
      <p class="empty-msg">Select an agent to start chatting.</p>
    {:else if messages.length === 0 && sessionId}
      <p class="empty-msg">Session started — say something.</p>
    {:else}
      {#each messages as msg}
        <div class="bubble {msg.role}">
          <div class="bubble-header">
            <span class="bubble-role">
              {msg.role === 'user' ? 'You' : agentName}
            </span>
            {#if msg.tokens}
              <span class="bubble-tokens">{msg.tokens} tokens</span>
            {/if}
          </div>
          <p class="bubble-text">{msg.text}</p>
        </div>
      {/each}
      {#if sending}
        <div class="bubble assistant thinking">
          <p class="bubble-text">…</p>
        </div>
      {/if}
    {/if}
  </div>

  <div class="input-row">
    <textarea
      bind:value={input}
      onkeydown={handleKeydown}
      placeholder="Type a message… (Enter to send, Shift+Enter for newline)"
      rows="2"
      disabled={!sessionId || sending}
      spellcheck="false"
    ></textarea>
    <button
      class="send-btn"
      onclick={sendMessage}
      disabled={!sessionId || !input.trim() || sending}
    >Send</button>
  </div>

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
    font-size: 0.875rem;
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
    font-size: 0.75rem;
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
    min-width: 220px;
  }
  select:disabled { opacity: 0.4; }

  .reset-btn {
    padding: 0.4rem 0.9rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--bg-surface);
    color: var(--text-muted);
    font-size: 0.85rem;
    cursor: pointer;
  }
  .reset-btn:hover:not(:disabled) {
    background: var(--bg-raised);
    color: var(--text);
  }
  .reset-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  .err-msg { color: var(--fail); font-size: 0.88rem; }
  .err     { color: var(--fail); font-size: 0.88rem; }
  .muted   { color: var(--text-muted); font-size: 0.88rem; }

  .transcript {
    flex: 1;
    overflow-y: auto;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg-surface);
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .empty-msg {
    color: var(--text-muted);
    font-size: 0.9rem;
    text-align: center;
    margin: auto;
  }

  .bubble {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    max-width: 85%;
  }
  .bubble.user    { align-self: flex-end; }
  .bubble.assistant { align-self: flex-start; }

  .bubble-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .bubble-role {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
  }
  .bubble-tokens {
    font-size: 0.68rem;
    color: var(--text-muted);
  }

  .bubble-text {
    background: var(--bg-raised);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.6rem 0.85rem;
    font-size: 0.9rem;
    line-height: 1.55;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .bubble.user .bubble-text {
    background: var(--accent-dim);
    border-color: rgba(76, 158, 255, 0.3);
  }
  .bubble.thinking .bubble-text {
    color: var(--text-muted);
    font-style: italic;
  }

  .input-row {
    display: flex;
    gap: 0.5rem;
    align-items: flex-end;
    flex-shrink: 0;
  }

  textarea {
    flex: 1;
    padding: 0.55rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 0.9rem;
    font-family: inherit;
    resize: none;
    background: var(--bg-surface);
    color: var(--text);
    line-height: 1.5;
  }
  textarea:disabled { opacity: 0.4; }
  textarea::placeholder { color: var(--text-muted); }
  textarea:focus { outline: none; border-color: var(--accent); }

  .send-btn {
    padding: 0.55rem 1.2rem;
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
  }
  .send-btn:hover:not(:disabled) { background: #3a8ef0; }
  .send-btn:disabled { background: rgba(76, 158, 255, 0.3); cursor: not-allowed; }
</style>
