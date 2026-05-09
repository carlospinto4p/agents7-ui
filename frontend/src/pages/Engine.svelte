<script>
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

  $effect(() => { fetchModels() })

  function fmtSize(bytes) {
    if (!bytes) return '—'
    const gb = bytes / 1e9
    return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(bytes / 1e6).toFixed(0)} MB`
  }
</script>

<div class="engine-page">
  <div class="page-header">
    <h2>Engine</h2>
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
  .engine-page { max-width: 820px; }

  .page-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }
  .page-header h2 { margin: 0; }

  button {
    padding: 0.35rem 0.9rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    background: #fff;
    cursor: pointer;
    font-size: 0.875rem;
  }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  button:hover:not(:disabled) { background: #f5f5f5; }

  h3 {
    margin: 0 0 0.75rem;
    font-size: 1rem;
    font-weight: 600;
  }
  .count { color: #888; font-weight: 400; }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
  }
  th, td {
    padding: 0.5rem 0.75rem;
    text-align: left;
    border-bottom: 1px solid #e0e0e0;
  }
  th {
    background: #f8f8f8;
    font-weight: 600;
    color: #444;
  }
  tr.loaded { background: #f3faf3; }

  .mono { font-family: monospace; font-size: 0.82rem; }

  .badge {
    display: inline-block;
    padding: 0.1rem 0.45rem;
    border-radius: 10px;
    font-size: 0.78rem;
    font-weight: 500;
  }
  .badge.green { background: #d4edda; color: #155724; }
  .badge.grey  { background: #e9ecef; color: #495057; }

  .msg { padding: 0.5rem 0; }
  .error { color: #c0392b; }
  .muted { color: #888; }
</style>
