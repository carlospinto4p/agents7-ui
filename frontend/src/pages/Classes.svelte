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

  // ── Layout constants (top-down tidy tree) ──────────────────
  const NODE_W = 224
  const NODE_H = 56
  const H_GAP = 26
  const ROW_H = 120
  const PAD = 24

  onMount(() => {
    fetch('/api/classes')
      .then((r) => r.json())
      .then((d) => {
        classes = d.classes ?? []
        loading = false
        if (classes.length) selectedName = classes[0].name
      })
      .catch((e) => {
        error = e.message
        loading = false
      })
  })

  // Build a tidy top-down tree layout from the flat parent-pointer
  // list: leaves are placed left→right in DFS order, internal nodes are
  // centered over their children, and depth sets the row. Families (the
  // three branches under the abstract root) get an index for colouring.
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

    let col = 0
    let maxDepth = 0
    const place = (node, depth) => {
      node.depth = depth
      maxDepth = Math.max(maxDepth, depth)
      if (node.children.length === 0) {
        node.col = col++
      } else {
        for (const ch of node.children) place(ch, depth + 1)
        const first = node.children[0].col
        const last = node.children[node.children.length - 1].col
        node.col = (first + last) / 2
      }
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

    const stepX = NODE_W + H_GAP
    const nodes = [...byName.values()]
    for (const n of nodes) {
      n.cx = PAD + n.col * stepX + NODE_W / 2
      n.cy = PAD + n.depth * ROW_H
    }
    const edges = []
    for (const n of nodes) {
      for (const ch of n.children) edges.push({ from: n, to: ch })
    }
    return {
      nodes,
      edges,
      width: PAD * 2 + Math.max(1, col) * stepX,
      height: PAD * 2 + maxDepth * ROW_H + NODE_H,
    }
  })

  // Bézier connector from a parent's bottom edge to a child's top edge.
  function edgePath(e) {
    const x1 = e.from.cx
    const y1 = e.from.cy + NODE_H
    const x2 = e.to.cx
    const y2 = e.to.cy
    const my = (y1 + y2) / 2
    return `M ${x1} ${y1} C ${x1} ${my}, ${x2} ${my}, ${x2} ${y2}`
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
            style="left:{n.cx - NODE_W / 2}px; top:{n.cy}px;
                   width:{NODE_W}px; height:{NODE_H}px"
            onclick={() => (selectedName = n.name)}
          >
            <span class="node-name">{n.name}</span>
            <span class="node-sub">{n.abstract ? 'abstract' : n.module}</span>
          </button>
        {/each}
      </div>
    </div>

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
              onclick={() => (selectedName = name)}
            >{name}</button>
          {/each}
        </div>

        {#if selected.doc}
          <p class="doc">{selected.doc}</p>
        {:else}
          <p class="doc muted">No docstring.</p>
        {/if}
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
  .ancestry.hidden { display: none; }

  .doc {
    color: var(--text);
    font-size: 1.0625rem;
    line-height: 1.6;
    white-space: pre-wrap;
    margin: 0;
  }
  .doc.muted { color: var(--text-muted); }
</style>
