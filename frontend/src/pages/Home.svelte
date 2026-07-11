<script>
  import { marked } from 'marked'

  let html = $state('')
  let loading = $state(true)
  let error = $state(null)
  let readmeEl = $state(null)

  $effect(() => {
    fetch('/api/readme')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.text()
      })
      .then(text => {
        html = enhanceReadme(marked(text))
        loading = false
      })
      .catch(e => {
        error = e.message
        loading = false
      })
  })

  // Delegate clicks on in-README anchor links (the Table of Contents).
  // The app uses hash routing, so we must NOT update location.hash —
  // instead expand the target's collapsed section and scroll to it.
  $effect(() => {
    const el = readmeEl
    if (!el) return
    el.addEventListener('click', onReadmeClick)
    return () => el.removeEventListener('click', onReadmeClick)
  })

  function slugify(text) {
    return text
      .trim()
      .toLowerCase()
      .replace(/[^\w\s-]/g, '')
      .replace(/\s/g, '-')
  }

  // Wrap each top-level (`##`) section in a collapsible <details>,
  // assign GitHub-style ids to every heading so the in-README Table of
  // Contents links resolve, and leave everything before the first `##`
  // (title + intro) always visible.
  function enhanceReadme(rawHtml) {
    const tpl = document.createElement('template')
    tpl.innerHTML = rawHtml
    const out = document.createElement('div')
    const seen = new Map()

    const uid = text => {
      const base = slugify(text)
      if (!seen.has(base)) {
        seen.set(base, 0)
        return base
      }
      const n = seen.get(base) + 1
      seen.set(base, n)
      return `${base}-${n}`
    }

    let body = null
    for (const node of Array.from(tpl.content.childNodes)) {
      const isHeading =
        node.nodeType === 1 && /^H[1-6]$/.test(node.tagName)
      if (node.nodeType === 1 && node.tagName === 'H2') {
        const details = document.createElement('details')
        details.className = 'readme-section'
        details.id = uid(node.textContent)
        const summary = document.createElement('summary')
        summary.innerHTML =
          `<span class="sec-title">${node.innerHTML}</span>`
        body = document.createElement('div')
        body.className = 'sec-body'
        details.append(summary, body)
        out.appendChild(details)
      } else {
        if (isHeading) node.id = uid(node.textContent)
        ;(body ?? out).appendChild(node)
      }
    }
    return out.innerHTML
  }

  function onReadmeClick(e) {
    const a = e.target.closest('a[href^="#"]')
    if (!a || !readmeEl?.contains(a)) return
    const href = a.getAttribute('href')
    if (href.startsWith('#/')) return
    const id = decodeURIComponent(href.slice(1))
    const target = id && readmeEl.querySelector(`#${CSS.escape(id)}`)
    if (!target) return
    e.preventDefault()
    for (
      let d = target.closest('details');
      d;
      d = d.parentElement?.closest('details')
    ) {
      d.open = true
    }
    target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
</script>

<div class="page-intro">
  <div class="intro-head">
    <h1 class="page-title">Framework</h1>
  </div>
  <p class="intro-desc">Python library for building LLM-based agents that return structured outputs via Pydantic models.</p>
</div>

{#if loading}
  <p class="state-msg">Loading…</p>
{:else if error}
  <p class="state-msg error">{error}</p>
{:else}
  <div class="readme" bind:this={readmeEl}>
    {@html html}
  </div>
{/if}

<style>
  .page-intro {
    max-width: 900px;
    margin: 0 auto 1.75rem;
  }
  .intro-head {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin: 0 0 0.4rem;
  }
  .page-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-strong);
    margin: 0;
  }
  .intro-desc {
    color: var(--text-muted);
    font-size: 1.0625rem;
    line-height: 1.6;
    margin: 0;
    max-width: 680px;
  }

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
  /* Collapsible top-level (##) sections */
  .readme :global(.readme-section) {
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg-surface);
    margin: 0.6rem 0;
    overflow: hidden;
  }
  .readme :global(.readme-section > summary) {
    list-style: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 0.65rem;
    padding: 0.7rem 1rem;
    font-size: 1.3rem;
    font-weight: 700;
    color: var(--text-strong);
    user-select: none;
    transition: background 0.12s ease;
  }
  .readme :global(.readme-section > summary::-webkit-details-marker) {
    display: none;
  }
  .readme :global(.readme-section > summary:hover) {
    background: var(--bg-raised);
  }
  .readme :global(.readme-section > summary::before) {
    content: '';
    width: 0.5rem;
    height: 0.5rem;
    border-right: 2px solid var(--accent);
    border-bottom: 2px solid var(--accent);
    transform: rotate(-45deg);
    transition: transform 0.15s ease;
    flex-shrink: 0;
  }
  .readme :global(.readme-section[open] > summary::before) {
    transform: rotate(45deg);
  }
  .readme :global(.readme-section[open] > summary) {
    border-bottom: 1px solid var(--border);
  }
  .readme :global(.sec-body) {
    padding: 0.25rem 1.25rem 0.75rem;
  }
  /* Tighten the first heading inside an open section */
  .readme :global(.sec-body > h3:first-child),
  .readme :global(.sec-body > h4:first-child) {
    margin-top: 0.75rem;
  }
  .readme :global(h3) {
    font-size: 1.0625rem;
    color: var(--text-strong);
    margin: 1.5rem 0 0.5rem;
  }
  .readme :global(h4) {
    font-size: 1.0625rem;
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
    font-size: 1.0625rem;
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
    font-size: 1.0625rem;
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
    font-size: 1.0625rem;
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
