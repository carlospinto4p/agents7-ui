<script>
  import { onMount } from 'svelte'

  let data = $state(null)
  let loading = $state(false)
  let error = $state(null)
  let busy = $state(new Set())
  let freeing = $state(false)
  let pollHandle = null

  let anyLoaded = $derived(
    (data?.models ?? []).some(m => m.loaded)
  )

  function anyLoadingNow() {
    return (data?.models ?? []).some(m => m.loading)
  }

  // Loads run server-side, so a model can be `loading` regardless of
  // which page started it. Poll while any model is loading; stop when
  // none are. Survives navigation: the state is refetched on mount.
  function syncPolling() {
    const need = anyLoadingNow()
    if (need && pollHandle === null) {
      pollHandle = setInterval(() => refetch(true), 2000)
    } else if (!need && pollHandle !== null) {
      clearInterval(pollHandle)
      pollHandle = null
    }
  }

  async function refetch(silent = false) {
    if (!silent) {
      loading = true
      error = null
    }
    try {
      const res = await fetch('/api/engine/models')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      data = await res.json()
    } catch (e) {
      if (!silent) error = e.message
    } finally {
      if (!silent) loading = false
    }
    syncPolling()
  }

  async function toggle(m) {
    if (busy.has(m.name) || m.loading) return
    busy = new Set(busy).add(m.name)
    const ep = m.loaded ? 'unload' : 'load'
    try {
      const res = await fetch(`/api/engine/${ep}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: m.name }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await refetch()
    } catch (e) {
      error = e.message
    } finally {
      const next = new Set(busy)
      next.delete(m.name)
      busy = next
    }
  }

  async function freeAll() {
    if (freeing) return
    freeing = true
    try {
      const res = await fetch('/api/engine/unload-all', { method: 'POST' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await refetch()
    } catch (e) {
      error = e.message
    } finally {
      freeing = false
    }
  }

  onMount(() => {
    refetch()
    return () => {
      if (pollHandle !== null) clearInterval(pollHandle)
    }
  })

  function fmtSize(bytes) {
    if (!bytes) return '—'
    const gb = bytes / 1e9
    return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(bytes / 1e6).toFixed(0)} MB`
  }
</script>

<div class="engine-page">
  <div class="page-header">
    <div>
      <h2>Engine</h2>
      <p class="intro-desc"><strong>Loaded</strong> — in VRAM, responds without delay. <strong>Idle</strong> — installed but not in memory, loads on the next request.</p>
    </div>
    <div class="header-actions">
      {#if anyLoaded}
        <button onclick={freeAll} disabled={freeing}>
          {#if freeing}<span class="spinner"></span>{/if}
          {freeing ? 'Freeing…' : 'Free all'}
        </button>
      {/if}
      <button onclick={() => refetch()} disabled={loading}>
        {#if loading}<span class="spinner"></span>{/if}
        {loading ? 'Loading…' : 'Refresh'}
      </button>
    </div>
  </div>

  {#if error}
    <p class="msg error">Error: {error}</p>
  {:else if data?.error}
    <p class="msg error">Ollama unreachable — {data.error}</p>
  {:else if !data}
    <p class="msg muted">Loading…</p>
  {:else if data.models.length === 0}
    <p class="msg muted">No models installed in Ollama.</p>
  {:else}
    <section>
      <h3>Models <span class="count">({data.models.length})</span></h3>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Size</th>
            <th>Status</th>
            <th>VRAM</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each data.models as m}
            <tr class:loaded={m.loaded}>
              <td class="mono">{m.name}</td>
              <td>{fmtSize(m.size)}</td>
              <td>
                {#if m.loaded}
                  <span class="badge green">loaded</span>
                {:else if m.loading}
                  <span class="badge warn"><span class="spinner"></span> loading</span>
                {:else}
                  <span class="badge grey">idle</span>
                {/if}
              </td>
              <td>{fmtSize(m.size_vram)}</td>
              <td>
                {#if m.loading}
                  <button class="act" disabled>
                    <span class="spinner"></span> Loading…
                  </button>
                {:else}
                  <button
                    class="act"
                    class:unload={m.loaded}
                    onclick={() => toggle(m)}
                    disabled={busy.has(m.name)}
                  >
                    {#if busy.has(m.name)}
                      <span class="spinner"></span>
                    {/if}
                    {m.loaded ? 'Unload' : 'Load'}
                  </button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>
  {/if}
</div>

<style>
  .engine-page { max-width: 820px; margin: 0 auto; }

  .page-header {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }
  .page-header h2 { margin: 0 0 0.35rem; color: var(--text-strong); }
  .intro-desc {
    color: var(--text-muted);
    font-size: 1.0625rem;
    line-height: 1.6;
    margin: 0;
    max-width: 600px;
  }

  .header-actions {
    display: flex;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  button {
    padding: 0.35rem 0.9rem;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--bg-surface);
    color: var(--text);
    cursor: pointer;
    font-size: 1.0625rem;
  }
  button:disabled { opacity: 0.4; cursor: not-allowed; }
  button:hover:not(:disabled) { background: var(--bg-raised); }

  .act {
    padding: 0.2rem 0.7rem;
    border-color: var(--accent);
    background: var(--accent-dim);
    color: var(--accent);
  }
  .act:hover:not(:disabled) {
    background: var(--accent);
    color: var(--bg);
  }
  .act.unload {
    border-color: var(--border);
    background: var(--bg-surface);
    color: var(--text-muted);
  }
  .act.unload:hover:not(:disabled) {
    background: var(--bg-raised);
    color: var(--text);
  }

  h3 {
    margin: 0 0 0.75rem;
    font-size: 1.0625rem;
    font-weight: 600;
    color: var(--text-strong);
  }
  .count { color: var(--text-muted); font-weight: 400; }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 1.0625rem;
  }
  th, td {
    padding: 0.5rem 0.75rem;
    text-align: left;
    border-bottom: 1px solid var(--border);
    color: var(--text);
  }
  th {
    background: var(--bg-raised);
    font-weight: 600;
    color: var(--text-muted);
    font-size: 1.0625rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  tr.loaded { background: rgba(63, 201, 126, 0.06); }

  .mono { font-family: monospace; font-size: 1.0625rem; }

  .badge {
    display: inline-block;
    padding: 0.1rem 0.45rem;
    border-radius: 10px;
    font-size: 1.0625rem;
    font-weight: 500;
  }
  .badge.green { background: var(--pass-bg); color: var(--pass); }
  .badge.grey  { background: var(--neutral-bg); color: var(--neutral); }
  .badge.warn  { background: var(--warn-bg); color: var(--warn); }

  .spinner {
    display: inline-block;
    width: 0.85em;
    height: 0.85em;
    border: 2px solid currentColor;
    border-right-color: transparent;
    border-radius: 50%;
    vertical-align: -0.12em;
    animation: spin 0.6s linear infinite;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .msg { padding: 0.5rem 0; }
  .error { color: var(--fail); }
  .muted { color: var(--text-muted); }
</style>
