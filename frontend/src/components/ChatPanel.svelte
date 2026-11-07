<script>
  import { metricsLine, downloadJson } from '../lib/format.js'

  // Reusable multi-turn chat panel for Chatter-family agents.
  // Owns the /api/chat session lifecycle for a single agent and
  // (re)starts the session whenever `agentName` changes. Used by
  // both the dedicated Chatter page and the inline runner on each
  // agent's catalog detail page.

  let {
    agentName,
    // Optional engine override. When `provider` is empty the session
    // uses the agent's configured engine; otherwise it starts with the
    // given provider/model. Changing either restarts the session.
    provider = '',
    model = '',
    // Per-conversation values for the agent's declared context_params
    // (e.g. the nickname of the person it is talking to). Changing
    // them restarts the session, since the system prompt is built
    // from them.
    context = {},
    sampleMessage = 'Hi! Tell me a bit about yourself.',
    placeholder = 'Type a message… (Enter to send, Shift+Enter for newline)',
  } = $props()

  let sessionId = $state(null)
  let messages  = $state([])   // [{ role, text, tokens? }]
  let input     = $state('')
  let sending   = $state(false)
  let starting  = $state(false)
  let chatError = $state(null)
  // Whether this agent's config lets it speak first. Reported by the
  // start response; false for every agent that was never given an
  // opening, which is most of them.
  let canOpen   = $state(false)
  // Whether this agent keeps a character fact store. Also from the
  // start response, and also false for most agents.
  let canRemember = $state(false)
  let remembering = $state(false)
  // What the last remember call wrote, for the line under the toolbar.
  let rememberNote = $state('')
  let transcriptEl

  // The context to send, serialised. Blank values are dropped so a
  // field left empty falls back to the agent's declared default.
  // Everything downstream reads this string rather than the object,
  // so a fresh-but-identical `context` (the page rebuilds it when the
  // agent changes) does not restart the session.
  let contextKey = $derived(
    JSON.stringify(
      Object.fromEntries(
        Object.entries(context ?? {}).filter(([, v]) =>
          String(v ?? '').trim(),
        ),
      ),
    ),
  )

  // (Re)start a session whenever the agent changes; the cleanup
  // tears down the previous session on change or unmount. Only
  // `agentName` is read synchronously here, so it is the sole
  // dependency — the session id is touched only in the untracked
  // cleanup, avoiding a self-triggering effect loop.
  $effect(() => {
    const name = agentName
    // Read the override synchronously so a provider/model change
    // restarts the session with the new engine.
    provider
    model
    // Same for the conversation context: it is baked into the system
    // prompt when the session starts, so it cannot change mid-chat.
    contextKey
    if (!name) return
    startSession(name)
    return () => {
      if (sessionId) {
        fetch(`/api/chat/${sessionId}`, { method: 'DELETE' })
      }
    }
  })

  // Keep the transcript pinned to the latest message.
  $effect(() => {
    messages.length
    if (transcriptEl) transcriptEl.scrollTop = transcriptEl.scrollHeight
  })

  // The start request body: an engine override when one is chosen,
  // and the conversation context when the agent declares any.
  function buildStartBody() {
    const body = provider ? { provider, model } : {}
    const ctx = JSON.parse(contextKey)
    if (Object.keys(ctx).length) body.context = ctx
    return body
  }

  async function startSession(name) {
    starting  = true
    chatError = null
    messages  = []
    sessionId = null
    canOpen   = false
    canRemember  = false
    rememberNote = ''
    try {
      const r = await fetch(
        `/api/chat/start/${encodeURIComponent(name)}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(buildStartBody()),
        },
      )
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        chatError = d.detail || `HTTP ${r.status}`
      } else {
        const d = await r.json()
        sessionId = d.session_id
        canOpen   = !!d.can_open
        canRemember = !!d.can_remember
        // Seed a ready-to-send example so the input is never blank.
        if (!input.trim()) input = sampleMessage
      }
    } catch (e) {
      chatError = e.message
    }
    starting = false
  }

  // Exposed to parents via bind:this — restarts with the same agent.
  export function restart() {
    if (sessionId) {
      fetch(`/api/chat/${sessionId}`, { method: 'DELETE' })
    }
    input = ''
    startSession(agentName)
  }

  // Stream one assistant turn into a fresh bubble at the end of the
  // transcript. `body` is the request payload, or null for a turn
  // that carries none (the opening one). The bubble is dropped again
  // if the turn fails before producing any text.
  async function streamTurn(url, body) {
    const idx = messages.length
    messages = [...messages, { role: 'assistant', text: '', meta: '' }]

    try {
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        ...(body ? { body: JSON.stringify(body) } : {}),
      })
      if (!r.ok || !r.body) {
        const d = await r.json().catch(() => ({}))
        chatError = d.detail || `HTTP ${r.status}`
        messages = messages.slice(0, idx)
      } else {
        await consumeSse(r.body, idx)
        // If the stream errored before any token, drop the empty bubble.
        if (chatError && !messages[idx]?.text) {
          messages = messages.slice(0, idx)
        }
      }
    } catch (e) {
      chatError = e.message
      messages = messages.slice(0, idx)
    }
  }

  async function sendMessage() {
    if (!sessionId || !input.trim() || sending) return
    const text = input.trim()
    input = ''
    sending = true
    chatError = null
    messages = [...messages, { role: 'user', text }]
    await streamTurn(`/api/chat/${sessionId}/stream`, { message: text })
    sending = false
  }

  // Ask the agent for the first line of the conversation. Deliberately
  // a click rather than something that fires when the session starts:
  // the session restarts whenever the agent, the engine override or a
  // context value changes, and each restart would otherwise spend a
  // model call nobody asked for.
  async function openTurn() {
    if (!sessionId || sending || messages.length) return
    sending = true
    chatError = null
    // The seeded example answers a question the agent has not asked
    // yet, so clear it and let the reply be the user's own.
    input = ''
    await streamTurn(`/api/chat/${sessionId}/open/stream`, null)
    sending = false
  }

  // Write what the agent said about itself into its fact store, so a
  // later conversation still knows it. A click for the same reason
  // openTurn is: it spends an LLM call, the session is torn down and
  // restarted on every agent, engine and context change, and only the
  // user knows whether this particular chat was worth keeping.
  async function rememberFacts() {
    if (!sessionId || sending || remembering || !messages.length) return
    remembering = true
    chatError = null
    rememberNote = ''
    try {
      const r = await fetch(`/api/chat/${sessionId}/remember`, {
        method: 'POST',
      })
      const d = await r.json().catch(() => ({}))
      if (!r.ok) {
        chatError = d.detail || `HTTP ${r.status}`
      } else {
        const facts = d.facts ?? []
        rememberNote = facts.length
          ? `Recorded: ${facts.join(' · ')}`
          : 'Nothing new to record.'
      }
    } catch (e) {
      chatError = e.message
    }
    remembering = false
  }

  // Read an SSE response body and dispatch each frame to handleFrame.
  async function consumeSse(body, idx) {
    const reader = body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let sep
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        handleFrame(buffer.slice(0, sep), idx)
        buffer = buffer.slice(sep + 2)
      }
    }
  }

  // Parse one SSE frame and apply it to the streaming bubble at `idx`.
  function handleFrame(frame, idx) {
    let event = 'message'
    let data = ''
    for (const line of frame.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) data += line.slice(5).trim()
    }
    if (!data) return
    let payload
    try {
      payload = JSON.parse(data)
    } catch {
      return
    }

    if (event === 'error') {
      chatError = payload.error || 'Chat error'
    } else if (event === 'done') {
      const meta = metricsLine(payload.metrics)
      messages = messages.map((m, i) => (i === idx ? { ...m, meta } : m))
    } else if (payload.delta) {
      messages = messages.map((m, i) =>
        i === idx ? { ...m, text: m.text + payload.delta } : m,
      )
    }
  }

  function downloadTranscript() {
    const name = agentName || 'chat'
    downloadJson(`chat-${name}.json`, messages)
  }

  // ── Save as read ────────────────────────────────────────
  // The download above writes `{role, text}`, which no read can
  // use: no per-call metrics, no guard verdicts, no context. This
  // writes the recording the Reads page reads, so a conversation
  // held here can be fed back on without being run again — and at
  // temperature, running it again is a different conversation.
  let savingRead = $state(false)
  let saveReadNote = $state('')
  let savedReadHref = $state('')
  let readId = $state(new Date().toISOString().slice(0, 10))
  let conversationId = $state('chat')
  let showSaveRead = $state(false)

  async function saveAsRead() {
    if (!sessionId || savingRead) return
    savingRead = true
    saveReadNote = ''
    savedReadHref = ''
    try {
      const r = await fetch(`/api/chat/${sessionId}/save-read`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          read_id: readId.trim(),
          conversation_id: conversationId.trim(),
        }),
      })
      const data = await r.json()
      if (!r.ok) {
        saveReadNote = data.detail ?? 'Could not save.'
        return
      }
      saveReadNote =
        `Saved ${data.turns} turns to ${data.path}/` +
        `${data.conversation_id}.json`
      savedReadHref =
        `#/reads?read=${encodeURIComponent(data.path)}` +
        `&conv=${encodeURIComponent(data.conversation_id)}`
      showSaveRead = false
    } catch {
      saveReadNote = 'Could not save.'
    } finally {
      savingRead = false
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }
</script>

<div class="chat-panel">
  {#if chatError}
    <p class="err-msg">{chatError}</p>
  {/if}

  {#if messages.length > 0}
    <div class="chat-toolbar">
      {#if canRemember}
        <button
          class="tool-btn"
          data-testid="remember-facts"
          onclick={rememberFacts}
          disabled={sending || remembering}
          title="Write what {agentName} said about itself into its
                 fact store, so later conversations know it"
        >
          {remembering ? 'Recording…' : '★ Remember'}
        </button>
      {/if}
      <button class="tool-btn" onclick={downloadTranscript}>
        ⬇ Transcript
      </button>
      <button
        class="tool-btn"
        data-testid="save-read"
        onclick={() => (showSaveRead = !showSaveRead)}
        disabled={sending || savingRead}
        title="Save this conversation as a read, so it can be
               reviewed and fed back on on the Reads page"
      >
        ⧉ Save as read
      </button>
    </div>
  {/if}

  {#if showSaveRead}
    <div class="save-read">
      <label>
        <span>Read</span>
        <input bind:value={readId} placeholder="2026-09-20" size="12" />
      </label>
      <label>
        <span>Conversation</span>
        <input bind:value={conversationId} placeholder="warm" size="10" />
      </label>
      <button
        class="tool-btn primary"
        onclick={saveAsRead}
        disabled={savingRead || !readId.trim() || !conversationId.trim()}
      >
        {savingRead ? 'Saving…' : 'Save'}
      </button>
      <span class="hint">
        Written beside the agent, under <code>docs/reads/</code>.
      </span>
    </div>
  {/if}

  {#if saveReadNote}
    <p
      class="remember-note"
      class:bad={saveReadNote.startsWith('Could not')}
      data-testid="save-read-note"
    >
      {saveReadNote}
      {#if savedReadHref}
        — <a href={savedReadHref} data-testid="open-read">open it on
        the Reads page</a>
      {/if}
    </p>
  {/if}

  {#if rememberNote}
    <p class="remember-note" data-testid="remember-note">{rememberNote}</p>
  {/if}

  <div class="transcript" bind:this={transcriptEl}>
    {#if starting}
      <p class="empty-msg">Starting session…</p>
    {:else if !sessionId}
      <p class="empty-msg">No session.</p>
    {:else if messages.length === 0 && canOpen}
      <div class="opening">
        <p class="empty-msg">
          Session started — say something, or let {agentName} open.
        </p>
        <button
          class="open-btn"
          data-testid="open-turn"
          onclick={openTurn}
          disabled={sending}
        >
          {sending ? 'Opening…' : `Let ${agentName} open`}
        </button>
      </div>
    {:else if messages.length === 0}
      <p class="empty-msg">Session started — say something.</p>
    {:else}
      {#each messages as msg}
        <div class="bubble {msg.role}" class:thinking={!msg.text}>
          <div class="bubble-header">
            <span class="bubble-role">
              {msg.role === 'user' ? 'You' : agentName}
            </span>
            {#if msg.meta}
              <span class="bubble-tokens">{msg.meta}</span>
            {/if}
          </div>
          <p class="bubble-text">{msg.text || '…'}</p>
        </div>
      {/each}
    {/if}
  </div>

  <div class="input-row">
    <textarea
      bind:value={input}
      onkeydown={handleKeydown}
      {placeholder}
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
  .chat-panel {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    height: 100%;
    width: 100%;
    min-height: 0;
  }

  .err-msg { color: var(--fail); font-size: 1.0625rem; margin: 0; }

  .chat-toolbar {
    display: flex;
    justify-content: flex-end;
    gap: 0.4rem;
  }
  .remember-note {
    margin: 0;
    color: var(--text-muted);
    font-size: 1.0625rem;
    text-align: right;
    overflow-wrap: anywhere;
  }
  .remember-note.bad {
    color: var(--fail);
  }

  /* ── Save as read ───────────────────────────────────── */
  .save-read {
    display: flex;
    align-items: flex-end;
    justify-content: flex-end;
    gap: 0.6rem;
    flex-wrap: wrap;
    padding: 0.45rem 0;
  }
  .save-read label {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }
  .save-read label span {
    font-size: 0.95rem;
    color: var(--text-muted);
  }
  .save-read input {
    background: var(--bg);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 0.35rem;
    padding: 0.25rem 0.45rem;
    font: inherit;
    font-size: 1.0625rem;
  }
  .save-read input:focus {
    outline: none;
    border-color: var(--accent);
  }
  .save-read .hint {
    flex-basis: 100%;
    text-align: right;
    font-size: 0.95rem;
    color: var(--text-muted);
  }
  .tool-btn.primary {
    border-color: var(--accent);
    background: var(--accent-dim);
    color: var(--accent);
    font-weight: 600;
  }
  .tool-btn {
    background: none;
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text-muted);
    font-size: 1.0625rem;
    padding: 0.2rem 0.6rem;
    cursor: pointer;
  }
  .tool-btn:hover:not(:disabled) {
    background: var(--bg-raised);
    color: var(--text);
  }
  .tool-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  .transcript {
    flex: 1;
    min-height: 0;
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
    font-size: 1.0625rem;
    text-align: center;
    margin: auto;
  }

  /* Empty-transcript state for an agent that may speak first. */
  .opening {
    margin: auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.75rem;
  }
  .open-btn {
    padding: 0.45rem 1rem;
    border: 1px solid var(--accent);
    border-radius: 8px;
    background: var(--accent-dim);
    color: var(--accent);
    font-size: 1.0625rem;
    font-weight: 600;
    cursor: pointer;
  }
  .open-btn:hover:not(:disabled) { background: var(--bg-raised); }
  .open-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  .bubble {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    max-width: 85%;
  }
  .bubble.user      { align-self: flex-end; }
  .bubble.assistant { align-self: flex-start; }

  .bubble-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .bubble-role {
    font-size: 1.0625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
  }
  .bubble-tokens {
    font-size: 1.0625rem;
    color: var(--text-muted);
  }

  .bubble-text {
    background: var(--bg-raised);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.6rem 0.85rem;
    font-size: 1.0625rem;
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
    font-size: 1.0625rem;
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
    font-size: 1.0625rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
  }
  .send-btn:hover:not(:disabled) { background: #3a8ef0; }
  .send-btn:disabled { background: rgba(76, 158, 255, 0.3); cursor: not-allowed; }
</style>
