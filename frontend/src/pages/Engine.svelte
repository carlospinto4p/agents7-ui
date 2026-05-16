<script>
  import { onMount } from 'svelte'

  let data = $state(null)
  let loading = $state(false)
  let error = $state(null)

  async function fetchModels() {
    loading = true
    error = null
    try {
      const res = await fetch('/api/engine/models')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      data = await res.json()
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
  }

  onMount(fetchModels)

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
    <button onclick={fetchModels} disabled={loading}>
      {loading ? 'Loading…' : 'Refresh'}
    </button>
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
                {:else}
                  <span class="badge grey">idle</span>
                {/if}
              </td>
              <td>{fmtSize(m.size_vram)}</td>
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
    font-size: 0.875rem;
    line-height: 1.6;
    margin: 0;
    max-width: 600px;
  }

  button {
    padding: 0.35rem 0.9rem;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--bg-surface);
    color: var(--text);
    cursor: pointer;
    font-size: 0.875rem;
  }
  button:disabled { opacity: 0.4; cursor: not-allowed; }
  button:hover:not(:disabled) { background: var(--bg-raised); }

  h3 {
    margin: 0 0 0.75rem;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-strong);
  }
  .count { color: var(--text-muted); font-weight: 400; }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
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
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  tr.loaded { background: rgba(63, 201, 126, 0.06); }

  .mono { font-family: monospace; font-size: 0.82rem; }

  .badge {
    display: inline-block;
    padding: 0.1rem 0.45rem;
    border-radius: 10px;
    font-size: 0.78rem;
    font-weight: 500;
  }
  .badge.green { background: var(--pass-bg); color: var(--pass); }
  .badge.grey  { background: var(--neutral-bg); color: var(--neutral); }

  .msg { padding: 0.5rem 0; }
  .error { color: var(--fail); }
  .muted { color: var(--text-muted); }
</style>
