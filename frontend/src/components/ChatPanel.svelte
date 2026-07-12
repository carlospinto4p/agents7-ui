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
    sampleMessage = 'Hi! Tell me a bit about yourself.',
    placeholder = 'Type a message… (Enter to send, Shift+Enter for newline)',
  } = $props()

  let sessionId = $state(null)
  let messages  = $state([])   // [{ role, text, tokens? }]
  let input     = $state('')
  let sending   = $state(false)
  let starting  = $state(false)
  let chatError = $state(null)
  let transcriptEl

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

  async function startSession(name) {
    starting  = true
    chatError = null
    messages  = []
    sessionId = null
    try {
      const r = await fetch(
        `/api/chat/start/${encodeURIComponent(name)}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(provider ? { provider, model } : {}),
        },
      )
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        chatError = d.detail || `HTTP ${r.status}`
      } else {
        const d = await r.json()
        sessionId = d.session_id
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

  async function sendMessage() {
    if (!sessionId || !input.trim() || sending) return
    const text = input.trim()
    input = ''
    sending = true
    chatError = null
    messages = [...messages, { role: 'user', text }]

    // Append an empty assistant bubble that fills as tokens stream in.
    const idx = messages.length
    messages = [...messages, { role: 'assistant', text: '', meta: '' }]

    try {
      const r = await fetch(`/api/chat/${sessionId}/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
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
    sending = false
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
      <button class="tool-btn" onclick={downloadTranscript}>
        ⬇ Transcript
      </button>
    </div>
  {/if}

  <div class="transcript" bind:this={transcriptEl}>
    {#if starting}
      <p class="empty-msg">Starting session…</p>
    {:else if !sessionId}
      <p class="empty-msg">No session.</p>
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

  .chat-toolbar { display: flex; justify-content: flex-end; }
  .tool-btn {
    background: none;
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text-muted);
    font-size: 1.0625rem;
    padding: 0.2rem 0.6rem;
    cursor: pointer;
  }
  .tool-btn:hover { background: var(--bg-raised); color: var(--text); }

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
