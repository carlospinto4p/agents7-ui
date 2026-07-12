<script>
  import { onMount } from 'svelte'

  // Agent class-hierarchy diagram. Data comes from the backend's
  // /api/classes endpoint, which introspects BaseAgent.__subclasses__()
  // at runtime — so this page needs no hardcoded class list and stays
  // correct as new agent classes are added to the framework.
  let classes = $state([])
  let loading = $state(true)
  let error = $state(null)
  let selectedName = $state(null)

  // ── Layout constants (left→right tidy tree) ────────────────
  // Depth grows rightward (each level is a column); sibling leaves
  // stack downward (each leaf is a row).
  const NODE_W = 220
  const NODE_H = 58
  const COL_GAP = 40
  const ROW_GAP = 24
  const PAD = 24
  const COL_W = NODE_W + COL_GAP
  const ROW_H = NODE_H + ROW_GAP

  // The selected class is deep-linkable as #/classes/<ClassName>, so a
  // specific class can be shared or bookmarked.
  function classFromHash() {
    const parts = window.location.hash.replace('#/', '').split('/')
    return parts[0] === 'classes' && parts[1]
      ? decodeURIComponent(parts[1])
      : null
  }

  function select(name) {
    selectedName = name
    // replaceState keeps the URL shareable without firing hashchange
    // (which would re-run the page router needlessly).
    history.replaceState(null, '', `#/classes/${encodeURIComponent(name)}`)
  }

  onMount(() => {
    fetch('/api/classes')
      .then((r) => r.json())
      .then((d) => {
        classes = d.classes ?? []
        loading = false
        const want = classFromHash()
        selectedName =
          (want && classes.some((c) => c.name === want)
            ? want
            : classes[0]?.name) ?? null
      })
      .catch((e) => {
        error = e.message
        loading = false
      })
  })

  // Build a tidy left→right tree from the flat parent-pointer list:
  // leaves are placed top→bottom in DFS order, internal nodes are
  // centered over their children's rows, and depth sets the column.
  let layout = $derived.by(() => {
    if (!classes.length) {
      return { nodes: [], edges: [], width: 0, height: 0 }
    }
    const byName = new Map(
      classes.map((c) => [c.name, { ...c, children: [] }])
    )
    let root = null
    for (const node of byName.values()) {
      const parent = node.parent ? byName.get(node.parent) : null
      if (parent) parent.children.push(node)
      else root = node
    }
    if (!root) return { nodes: [], edges: [], width: 0, height: 0 }

    let row = 0
    let maxDepth = 0
    let maxRow = 0
    const place = (node, depth) => {
      node.depth = depth
      maxDepth = Math.max(maxDepth, depth)
      if (node.children.length === 0) {
        node.row = row++
      } else {
        for (const ch of node.children) place(ch, depth + 1)
        const first = node.children[0].row
        const last = node.children[node.children.length - 1].row
        node.row = (first + last) / 2
      }
      maxRow = Math.max(maxRow, node.row)
    }
    place(root, 0)

    // Colour by branch: the abstract root is neutral; each depth-1
    // child seeds a family that its whole subtree inherits.
    const paint = (node, fam) => {
      node.famIndex = fam
      for (const ch of node.children) paint(ch, fam)
    }
    root.famIndex = -1
    root.children.forEach((ch, i) => paint(ch, i))

    const nodes = [...byName.values()]
    for (const n of nodes) {
      n.x = PAD + n.depth * COL_W
      n.y = PAD + n.row * ROW_H
    }
    const edges = []
    for (const n of nodes) {
      for (const ch of n.children) edges.push({ from: n, to: ch })
    }
    return {
      nodes,
      edges,
      width: PAD * 2 + maxDepth * COL_W + NODE_W,
      height: PAD * 2 + maxRow * ROW_H + NODE_H,
    }
  })

  // Bézier connector from a parent's right edge to a child's left edge.
  function edgePath(e) {
    const x1 = e.from.x + NODE_W
    const y1 = e.from.y + NODE_H / 2
    const x2 = e.to.x
    const y2 = e.to.y + NODE_H / 2
    const mx = (x1 + x2) / 2
    return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`
  }

  function famClass(node) {
    return node.famIndex < 0 ? 'fam-base' : `fam-${node.famIndex % 3}`
  }

  let selected = $derived(
    classes.find((c) => c.name === selectedName) ?? null
  )

  // Inheritance chain from BaseAgent down to the selected class.
  let ancestry = $derived.by(() => {
    if (!selected) return []
    const byName = new Map(classes.map((c) => [c.name, c]))
    const chain = []
    let cur = selected
    while (cur) {
      chain.unshift(cur.name)
      cur = cur.parent ? byName.get(cur.parent) : null
    }
    return chain
  })

  // Description prose split into paragraphs for rendering.
  let descParas = $derived(
    (selected?.description ?? '').split('\n\n').filter(Boolean)
  )

  // Split docstring text into plain/inline-code runs so reST markup
  // (`name` or ``name``) renders as <code> instead of literal backticks.
  function tokens(text) {
    const parts = []
    const re = /``([^`]+)``|`([^`]+)`/g
    let last = 0
    let m
    while ((m = re.exec(text)) !== null) {
      if (m.index > last) {
        parts.push({ code: false, t: text.slice(last, m.index) })
      }
      parts.push({ code: true, t: m[1] ?? m[2] })
      last = re.lastIndex
    }
    if (last < text.length) parts.push({ code: false, t: text.slice(last) })
    return parts
  }

  // Group the class's fields by the ancestor that introduced them, in
  // inheritance order (base-most first) — the fields list already
  // arrives base→derived, so contiguous same-owner runs form groups.
  let fieldGroups = $derived.by(() => {
    const groups = []
    for (const f of selected?.fields ?? []) {
      const last = groups[groups.length - 1]
      if (last && last.owner === f.owner) last.items.push(f)
      else groups.push({ owner: f.owner, inherited: f.inherited, items: [f] })
    }
    return groups
  })
</script>

<div class="classes">
  <div class="page-intro">
    <h1 class="page-title">Agent Classes</h1>
    <p class="intro-desc">
      The agent class hierarchy in <strong>agents7</strong>, rooted at the
      abstract <code>BaseAgent</code>. Click a class to see what it does
      and how it inherits. Introspected live from the framework, so it
      always matches the installed version.
    </p>
  </div>

  {#if loading}
    <p class="state-msg">Loading class hierarchy…</p>
  {:else if error}
    <p class="state-msg error">{error}</p>
  {:else}
    <div class="legend">
      <span class="legend-item"><span class="swatch fam-base"></span> abstract base</span>
      {#each layout.nodes.filter((n) => n.depth === 1) as branch}
        <span class="legend-item">
          <span class="swatch {famClass(branch)}"></span>
          {branch.name} family
        </span>
      {/each}
    </div>

    <div class="diagram-scroll">
      <div
        class="canvas"
        style="width:{layout.width}px; height:{layout.height}px"
      >
        <svg
          class="edges"
          width={layout.width}
          height={layout.height}
          aria-hidden="true"
        >
          {#each layout.edges as e}
            <path class="edge" d={edgePath(e)} />
          {/each}
        </svg>

        {#each layout.nodes as n (n.name)}
          <button
            class="node {famClass(n)}"
            class:abstract={n.abstract}
            class:selected={n.name === selectedName}
            style="left:{n.x}px; top:{n.y}px;
                   width:{NODE_W}px; height:{NODE_H}px"
            title={n.name}
            onclick={() => select(n.name)}
          >
            <span class="node-name">{n.name}</span>
            <span class="node-sub">{n.abstract ? 'abstract' : n.module}</span>
          </button>
        {/each}
      </div>
    </div>

    {#snippet rich(text)}
      {#each tokens(text) as tok}{#if tok.code}<code class="inline-code">{tok.t}</code>{:else}{tok.t}{/if}{/each}
    {/snippet}

    {#if selected}
      <div class="detail">
        <div class="detail-head">
          <h2>{selected.name}</h2>
          <span class="badge {selected.abstract ? 'abstract-badge' : 'concrete-badge'}">
            {selected.abstract ? 'abstract' : 'concrete'}
          </span>
          <span class="badge module-badge">{selected.module}.py</span>
        </div>

        <div class="ancestry" class:hidden={ancestry.length <= 1}>
          {#each ancestry as name, i}
            {#if i > 0}<span class="arrow">→</span>{/if}
            <button
              class="crumb"
              class:current={name === selectedName}
              onclick={() => select(name)}
            >{name}</button>
          {/each}
        </div>

        {#if selected.summary}
          <p class="lead">{selected.summary}</p>
        {/if}
        {#each descParas as p}
          <p class="doc">{@render rich(p)}</p>
        {/each}

        {#if fieldGroups.length}
          <div class="doc-section">
            <h3 class="doc-section-title">Attributes &amp; Parameters</h3>
            <p class="section-hint">
              Grouped by the class that introduced each field. Every
              agent's constructor parameters are its dataclass fields.
            </p>
            {#each fieldGroups as g}
              <details open class="field-group">
                <summary class="group-title">
                  {#if g.inherited}
                    <span class="group-tag inherited">inherited</span>
                    <span class="group-owner">{g.owner}</span>
                  {:else}
                    <span class="group-tag own">defined here</span>
                    <span class="group-owner">{selected.name}</span>
                  {/if}
                  <span class="group-count">
                    {g.items.length} field{g.items.length === 1 ? '' : 's'}
                  </span>
                </summary>
                <dl class="fields">
                  {#each g.items as item}
                    <div class="field">
                      <dt>
                        <code class="field-name">{item.name}</code>
                        {#if item.type}<span class="field-type">{item.type}</span>{/if}
                      </dt>
                      <dd>{#if item.text}{@render rich(item.text)}{:else}—{/if}</dd>
                    </div>
                  {/each}
                </dl>
              </details>
            {/each}
          </div>
        {/if}

        {#each selected.sections ?? [] as section}
          <div class="doc-section">
            <h3 class="doc-section-title">{section.title}</h3>
            {#each section.text.split('\n\n').filter(Boolean) as p}
              <p class="doc">{@render rich(p)}</p>
            {/each}
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>

<style>
  .classes {
    max-width: 1200px;
    margin: 0 auto;
  }

  .page-intro {
    margin-bottom: 1.5rem;
  }
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
    max-width: 720px;
  }
  .intro-desc code {
    font-family: ui-monospace, 'Cascadia Code', monospace;
    color: var(--text);
  }

  .state-msg {
    color: var(--text-muted);
    font-size: 1.0625rem;
    margin: 2rem 0;
  }
  .state-msg.error {
    color: var(--fail);
  }

  /* ── Legend ─────────────────────────────────────────────── */
  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    margin-bottom: 1rem;
    font-size: 1.0625rem;
    color: var(--text-muted);
  }
  .legend-item {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
  }
  .swatch {
    width: 0.85rem;
    height: 0.85rem;
    border-radius: 3px;
    border: 1px solid var(--border);
  }

  /* ── Diagram canvas ─────────────────────────────────────── */
  .diagram-scroll {
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: var(--bg-surface);
    padding: 0.5rem;
    scrollbar-width: thin;
    scrollbar-color: var(--border) transparent;
  }
  .canvas {
    position: relative;
    margin: 0 auto;
  }
  .edges {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }
  .edge {
    fill: none;
    stroke: var(--border);
    stroke-width: 1.6;
  }

  /* ── Nodes ──────────────────────────────────────────────── */
  .node {
    position: absolute;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    justify-content: center;
    gap: 0.15rem;
    padding: 0 0.75rem;
    border: 1.5px solid var(--border);
    border-left-width: 4px;
    border-radius: 8px;
    background: var(--bg-raised);
    cursor: pointer;
    text-align: left;
    transition: transform 0.12s, box-shadow 0.12s, border-color 0.12s;
  }
  .node:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4);
  }
  .node.abstract {
    border-style: dashed;
  }
  .node.selected {
    box-shadow: 0 0 0 2px var(--accent);
  }
  .node-name {
    font-family: ui-monospace, 'Cascadia Code', monospace;
    font-weight: 700;
    font-size: 1.0625rem;
    color: var(--text-strong);
    line-height: 1.2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
  }
  .node-sub {
    font-size: 0.85rem;
    color: var(--text-muted);
    font-family: ui-monospace, 'Cascadia Code', monospace;
  }

  /* Family accent colours use the shared semantic tokens. */
  .fam-base { border-left-color: var(--text-muted); }
  .fam-0 { border-left-color: var(--accent); }
  .fam-1 { border-left-color: var(--pass); }
  .fam-2 { border-left-color: var(--warn); }
  .swatch.fam-base { background: var(--text-muted); }
  .swatch.fam-0 { background: var(--accent); }
  .swatch.fam-1 { background: var(--pass); }
  .swatch.fam-2 { background: var(--warn); }

  /* ── Detail panel ───────────────────────────────────────── */
  .detail {
    margin-top: 1.5rem;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: var(--bg-surface);
    padding: 1.1rem 1.25rem;
  }
  .detail-head {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
    margin-bottom: 0.6rem;
  }
  .detail-head h2 {
    font-family: ui-monospace, 'Cascadia Code', monospace;
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--text-strong);
    margin: 0;
  }
  .badge {
    display: inline-flex;
    align-items: center;
    padding: 0.1rem 0.55rem;
    border-radius: 999px;
    font-size: 0.9rem;
    font-weight: 500;
    letter-spacing: 0.01em;
  }
  .abstract-badge { background: var(--neutral-bg); color: var(--neutral); }
  .concrete-badge { background: var(--pass-bg); color: var(--pass); }
  .module-badge {
    background: var(--info-bg);
    color: var(--accent);
    font-family: ui-monospace, 'Cascadia Code', monospace;
  }

  .ancestry {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.3rem;
    margin-bottom: 0.85rem;
  }
  .ancestry.hidden { display: none; }
  .crumb {
    background: none;
    border: none;
    padding: 0;
    font-family: ui-monospace, 'Cascadia Code', monospace;
    font-size: 1.0625rem;
    color: var(--text-muted);
    cursor: pointer;
  }
  .crumb:hover { color: var(--accent); text-decoration: underline; }
  .crumb.current { color: var(--text-strong); font-weight: 700; cursor: default; }
  .arrow { color: var(--text-muted); opacity: 0.5; }

  .lead {
    color: var(--text-strong);
    font-size: 1.0625rem;
    font-weight: 600;
    line-height: 1.55;
    margin: 0 0 0.6rem;
  }
  .doc {
    color: var(--text);
    font-size: 1.0625rem;
    line-height: 1.6;
    margin: 0 0 0.6rem;
  }
  .doc:last-child { margin-bottom: 0; }

  .inline-code {
    font-family: ui-monospace, 'Cascadia Code', monospace;
    font-size: 0.95em;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.02rem 0.3rem;
    color: var(--text-strong);
  }

  /* ── Parsed docstring sections ──────────────────────────── */
  .doc-section {
    margin-top: 1.1rem;
    padding-top: 0.9rem;
    border-top: 1px solid var(--border);
  }
  .doc-section-title {
    font-size: 1.0625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--text-muted);
    margin: 0 0 0.65rem;
  }
  .fields {
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }
  .field {
    display: grid;
    grid-template-columns: minmax(140px, 200px) 1fr;
    gap: 0.75rem;
    align-items: baseline;
  }
  .field dt {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.35rem;
    min-width: 0;
  }
  .field dd {
    margin: 0;
    color: var(--text);
    font-size: 1.0625rem;
    line-height: 1.55;
  }
  .field-name {
    font-family: ui-monospace, 'Cascadia Code', monospace;
    font-size: 1.0625rem;
    font-weight: 700;
    color: var(--text-strong);
    overflow-wrap: anywhere;
  }
  .field-type {
    font-family: ui-monospace, 'Cascadia Code', monospace;
    font-size: 0.9rem;
    color: var(--accent);
    background: var(--info-bg);
    border-radius: 4px;
    padding: 0.02rem 0.35rem;
    overflow-wrap: anywhere;
  }

  /* ── Field groups (by origin class) ─────────────────────── */
  .section-hint {
    color: var(--text-muted);
    font-size: 1.0625rem;
    line-height: 1.5;
    margin: -0.35rem 0 0.9rem;
  }
  .field-group {
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg-raised);
    padding: 0.6rem 0.85rem;
    margin-bottom: 0.7rem;
  }
  .field-group:last-child {
    margin-bottom: 0;
  }
  .field-group[open] > .group-title {
    margin-bottom: 0.7rem;
  }
  .group-title {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    cursor: pointer;
    list-style: none;
    font-size: 1.0625rem;
  }
  .group-title::-webkit-details-marker {
    display: none;
  }
  /* Disclosure triangle drawn from the summary so it rotates on open. */
  .group-title::before {
    content: '▸';
    color: var(--text-muted);
    font-size: 0.9rem;
    transition: transform 0.15s;
  }
  .field-group[open] > .group-title::before {
    transform: rotate(90deg);
  }
  .group-tag {
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 700;
    padding: 0.05rem 0.5rem;
    border-radius: 999px;
  }
  .group-tag.inherited {
    background: var(--neutral-bg);
    color: var(--neutral);
  }
  .group-tag.own {
    background: var(--pass-bg);
    color: var(--pass);
  }
  .group-owner {
    font-family: ui-monospace, 'Cascadia Code', monospace;
    font-weight: 700;
    color: var(--text-strong);
  }
  .group-count {
    margin-left: auto;
    font-size: 0.9rem;
    color: var(--text-muted);
  }

  /* Stack the field label above its description on narrow widths. */
  @media (max-width: 640px) {
    .field {
      grid-template-columns: 1fr;
      gap: 0.2rem;
    }
  }
</style>
