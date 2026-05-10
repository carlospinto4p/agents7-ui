<script>
  import { marked } from 'marked'

  let html = $state('')
  let loading = $state(true)
  let error = $state(null)

  $effect(() => {
    fetch('/api/readme')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.text()
      })
      .then(text => {
        html = marked(text)
        loading = false
      })
      .catch(e => {
        error = e.message
        loading = false
      })
  })
</script>

{#if loading}
  <p class="state-msg">Loading…</p>
{:else if error}
  <p class="state-msg error">{error}</p>
{:else}
  <div class="readme">
    {@html html}
  </div>
{/if}

<style>
  .state-msg {
    color: var(--text-muted);
    padding: 2rem 0;
  }
  .state-msg.error { color: var(--fail); }

  .readme {
    max-width: 900px;
    margin: 0 auto;
    line-height: 1.65;
  }

  /* Headings */
  .readme :global(h1) {
    font-size: 1.75rem;
    color: var(--text-strong);
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.5rem;
    margin: 0 0 1rem;
  }
  .readme :global(h2) {
    font-size: 1.3rem;
    color: var(--text-strong);
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.35rem;
    margin: 2rem 0 0.75rem;
  }
  .readme :global(h3) {
    font-size: 1.05rem;
    color: var(--text-strong);
    margin: 1.5rem 0 0.5rem;
  }
  .readme :global(h4) {
    font-size: 0.95rem;
    color: var(--text-strong);
    margin: 1.25rem 0 0.4rem;
  }

  /* Paragraphs and inline */
  .readme :global(p) { margin: 0.65rem 0; }
  .readme :global(strong) { color: var(--text-strong); }
  .readme :global(a) { color: var(--accent); }
  .readme :global(hr) {
    border: none;
    border-top: 1px solid var(--border);
    margin: 1.5rem 0;
  }

  /* Inline code */
  .readme :global(code) {
    background: var(--bg-raised);
    border: 1px solid var(--border);
    padding: 0.1em 0.35em;
    border-radius: 3px;
    font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
    font-size: 0.865em;
    color: var(--accent);
  }

  /* Code blocks */
  .readme :global(pre) {
    background: var(--bg-raised);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1rem 1.25rem;
    overflow-x: auto;
    margin: 0.75rem 0;
  }
  .readme :global(pre code) {
    background: none;
    border: none;
    padding: 0;
    color: var(--text);
    font-size: 0.875rem;
  }

  /* Lists */
  .readme :global(ul),
  .readme :global(ol) {
    padding-left: 1.6rem;
    margin: 0.5rem 0;
  }
  .readme :global(li) { margin: 0.2rem 0; }
  .readme :global(li > p) { margin: 0.2rem 0; }

  /* Tables */
  .readme :global(table) {
    border-collapse: collapse;
    width: 100%;
    margin: 0.75rem 0;
    font-size: 0.9rem;
  }
  .readme :global(th),
  .readme :global(td) {
    border: 1px solid var(--border);
    padding: 0.45rem 0.75rem;
    text-align: left;
  }
  .readme :global(th) {
    background: var(--bg-raised);
    color: var(--text-strong);
    font-weight: 600;
  }
  .readme :global(tr:nth-child(even) td) {
    background: var(--bg-surface);
  }

  /* Blockquote */
  .readme :global(blockquote) {
    border-left: 3px solid var(--accent);
    padding: 0.25rem 1rem;
    color: var(--text-muted);
    margin: 0.75rem 0;
    background: var(--accent-dim);
    border-radius: 0 4px 4px 0;
  }
</style>
