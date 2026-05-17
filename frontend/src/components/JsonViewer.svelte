<script>
  /** @type {{ value: unknown, maxHeight?: string }} */
  let { value, maxHeight = '340px' } = $props();

  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function render(v, depth) {
    const pad = '  '.repeat(depth);
    const inner = '  '.repeat(depth + 1);

    if (v === null || v === undefined)
      return `<span class="jv-null">${v === null ? 'null' : 'undefined'}</span>`;
    if (typeof v === 'boolean')
      return `<span class="jv-bool">${v}</span>`;
    if (typeof v === 'number')
      return `<span class="jv-num">${v}</span>`;
    if (typeof v === 'string')
      return `<span class="jv-str">"${esc(v)}"</span>`;

    if (Array.isArray(v)) {
      if (v.length === 0)
        return '<span class="jv-p">[]</span>';
      const items = v
        .map(item => `${inner}${render(item, depth + 1)}`)
        .join('<span class="jv-p">,</span>\n');
      return `<span class="jv-p">[</span>\n${items}\n${pad}<span class="jv-p">]</span>`;
    }

    if (typeof v === 'object') {
      const keys = Object.keys(v);
      if (keys.length === 0)
        return '<span class="jv-p">{}</span>';
      const items = keys
        .map(k =>
          `${inner}<span class="jv-key">"${esc(k)}"</span><span class="jv-p">: </span>${render(v[k], depth + 1)}`
        )
        .join('<span class="jv-p">,</span>\n');
      return `<span class="jv-p">{</span>\n${items}\n${pad}<span class="jv-p">}</span>`;
    }

    return esc(String(v));
  }

  let html = $derived(render(value, 0));
</script>

<pre class="json-viewer" style="max-height: {maxHeight}">{@html html}</pre>

<style>
  .json-viewer {
    background: var(--bg-raised);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.85rem 1rem;
    font-size: 0.8rem;
    line-height: 1.6;
    font-family: ui-monospace, 'Cascadia Code', 'Fira Code', monospace;
    color: var(--text);
    margin: 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    overflow-y: auto;
    overflow-x: hidden;
    scrollbar-width: thin;
    scrollbar-color: var(--border) transparent;
  }

  .json-viewer::-webkit-scrollbar        { width: 5px; }
  .json-viewer::-webkit-scrollbar-track  { background: transparent; }
  .json-viewer::-webkit-scrollbar-thumb  { background: var(--border); border-radius: 3px; }
  .json-viewer::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

  :global(.jv-key)  { color: #4c9eff; }
  :global(.jv-str)  { color: #85e89d; }
  :global(.jv-num)  { color: #ffa657; }
  :global(.jv-bool) { color: #ff9a5c; }
  :global(.jv-null) { color: #ff9a5c; font-style: italic; }
  :global(.jv-p)    { color: var(--text-muted); }
</style>
