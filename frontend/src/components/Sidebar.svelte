<script>
  // Lateral navigation menu, mirroring the market_wrapper sidebar
  // style. Uses the project's CSS custom-property design tokens and
  // inline SVG icons (no icon dependency).

  let {
    page = 'home',
    name = '',
    version = '',
    ollamaStatus = 'checking',
    canStart = false,
    starting = false,
    onstart = () => {},
  } = $props()

  // ── Drag-to-resize ──────────────────────────────────────
  // Width is user-adjustable via the right-edge handle and
  // persisted across sessions in localStorage. Clamped so the
  // sidebar can never collapse below its icons+labels or grow
  // past a sensible share of the viewport.
  const MIN_WIDTH = 180
  const MAX_WIDTH = 420
  const DEFAULT_WIDTH = 300
  const STORAGE_KEY = 'agents7.sidebarWidth'

  function loadWidth() {
    const raw = Number(localStorage.getItem(STORAGE_KEY))
    return raw >= MIN_WIDTH && raw <= MAX_WIDTH ? raw : DEFAULT_WIDTH
  }

  let width = $state(loadWidth())
  let dragging = $state(false)

  function startResize(e) {
    e.preventDefault()
    dragging = true
    const startX = e.clientX
    const startW = width
    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'col-resize'

    const onMove = (ev) => {
      const next = startW + (ev.clientX - startX)
      width = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, next))
    }
    const onUp = () => {
      dragging = false
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
      localStorage.setItem(STORAGE_KEY, String(width))
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  function resetWidth() {
    width = DEFAULT_WIDTH
    localStorage.setItem(STORAGE_KEY, String(width))
  }

  // Keyboard resizing: focus the handle and nudge with arrows.
  function onHandleKey(e) {
    const step = e.shiftKey ? 24 : 8
    let next = width
    if (e.key === 'ArrowLeft') next = width - step
    else if (e.key === 'ArrowRight') next = width + step
    else if (e.key === 'Home') next = MIN_WIDTH
    else if (e.key === 'End') next = MAX_WIDTH
    else return
    e.preventDefault()
    width = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, next))
    localStorage.setItem(STORAGE_KEY, String(width))
  }

  // Each nav item carries the SVG inner markup for its icon (24x24,
  // stroke-based to match a clean line-icon look).
  const nav = [
    {
      key: 'home',
      label: 'Home',
      icon: '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
    },
    {
      key: 'catalog',
      label: 'Catalog',
      icon: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>',
    },
    {
      key: 'runner',
      label: 'Runner',
      icon: '<polygon points="6 3 20 12 6 21 6 3"/>',
    },
    {
      key: 'chatter',
      label: 'Chatter',
      icon: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    },
    {
      key: 'engine',
      label: 'Engine',
      icon: '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/>',
    },
    {
      key: 'eval',
      label: 'Eval',
      icon: '<path d="M3 3v18h18"/><path d="M18 17V9M13 17V5M8 17v-3"/>',
    },
  ]
</script>

<aside class="sidebar" class:dragging style="width: {width}px">
  <div class="brand">
    <div class="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 32 32" fill="none">
        <path
          d="M6 22 L11 10 L16 18 L21 12 L26 22"
          stroke="currentColor"
          stroke-width="2.4"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <circle cx="26" cy="22" r="1.8" fill="currentColor" />
      </svg>
    </div>
    <div class="brand-text">
      <div class="brand-name">{name || 'agents7'}</div>
      <div class="brand-sub">{version ? `v${version}` : ''}</div>
    </div>
  </div>

  <nav class="nav">
    {#each nav as item (item.key)}
      {@const active = page === item.key}
      <a
        href={`#/${item.key}`}
        class="nav-item"
        class:active
        aria-current={active ? 'page' : undefined}
      >
        <svg
          class="nav-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width={active ? 2.2 : 1.8}
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          {@html item.icon}
        </svg>
        <span>{item.label}</span>
        {#if active}
          <span class="nav-dot"></span>
        {/if}
      </a>
    {/each}
  </nav>

  <div class="engine-block">
    <div
      class="ollama-pill"
      class:up={ollamaStatus === 'up'}
      class:down={ollamaStatus === 'down'}
    >
      <span class="dot"></span>
      <span>Ollama</span>
    </div>
    {#if ollamaStatus === 'down' && canStart}
      <button class="start-btn" onclick={onstart} disabled={starting}>
        {starting ? 'Starting…' : 'Start'}
      </button>
    {/if}
  </div>

  <!-- Right-edge grab strip: drag to resize, arrows to nudge,
       double-click to reset. A native button is interactive and
       focusable, so it needs no role/tabindex a11y overrides. -->
  <button
    type="button"
    class="resize-handle"
    aria-label="Resize sidebar"
    onmousedown={startResize}
    ondblclick={resetWidth}
    onkeydown={onHandleKey}
  ></button>
</aside>

<style>
  .sidebar {
    position: relative;
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    height: 100%;
    border-right: 1px solid var(--border);
    background: var(--bg-surface);
  }

  /* ── Resize handle ──────────────────────────────────── */
  .resize-handle {
    position: absolute;
    top: 0;
    right: -3px;
    width: 6px;
    height: 100%;
    padding: 0;
    border: none;
    background: transparent;
    appearance: none;
    cursor: col-resize;
    z-index: 5;
    transition: background 0.12s ease;
  }
  .resize-handle:hover,
  .sidebar.dragging .resize-handle {
    background: var(--accent-dim);
  }
  .resize-handle:focus-visible {
    outline: none;
    background: var(--accent);
  }

  /* ── Brand ──────────────────────────────────────────── */
  .brand {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    padding: 1.1rem 1.15rem;
  }
  .brand-mark {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2.15rem;
    height: 2.15rem;
    border-radius: 0.6rem;
    color: var(--accent);
    background: var(--accent-dim);
    border: 1px solid var(--accent);
    flex-shrink: 0;
  }
  .brand-mark svg {
    width: 1.2rem;
    height: 1.2rem;
  }
  .brand-text {
    line-height: 1.2;
    min-width: 0;
  }
  .brand-name {
    font-weight: 700;
    font-size: 1.3rem;
    letter-spacing: -0.4px;
    color: var(--text-strong);
  }
  .brand-sub {
    font-family: ui-monospace, 'Cascadia Code', monospace;
    font-size: 1.0625rem;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* ── Nav ────────────────────────────────────────────── */
  .nav {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    flex: 1;
    padding: 0.4rem 0.6rem;
    overflow-y: auto;
  }
  .nav-item {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    padding: 0.5rem 0.7rem;
    border-radius: 0.55rem;
    color: var(--text-muted);
    font-size: 1.0625rem;
    text-decoration: none;
    border: 1px solid transparent;
    transition: background 0.12s ease, color 0.12s ease;
  }
  .nav-item:hover {
    background: var(--bg-raised);
    color: var(--text-strong);
    text-decoration: none;
  }
  .nav-item.active {
    background: var(--accent-dim);
    color: var(--accent);
    border-color: var(--accent);
    font-weight: 600;
  }
  .nav-icon {
    width: 1.15rem;
    height: 1.15rem;
    flex-shrink: 0;
  }
  .nav-dot {
    margin-left: auto;
    width: 0.4rem;
    height: 0.4rem;
    border-radius: 50%;
    background: var(--accent);
    flex-shrink: 0;
  }

  /* ── Engine status ──────────────────────────────────── */
  .engine-block {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.85rem 1.15rem;
    border-top: 1px solid var(--border);
  }
  .ollama-pill {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 1.0625rem;
    color: var(--neutral);
    padding: 0.2rem 0.55rem;
    border-radius: 10px;
    background: var(--neutral-bg);
    border: 1px solid transparent;
    user-select: none;
  }
  .ollama-pill.up {
    color: var(--pass);
    background: var(--pass-bg);
  }
  .ollama-pill.down {
    color: var(--fail);
    background: var(--fail-bg);
  }
  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
    flex-shrink: 0;
  }
  .start-btn {
    border: 1px solid var(--accent);
    background: var(--accent-dim);
    color: var(--accent);
    font-size: 1.0625rem;
    font-weight: 600;
    padding: 0.2rem 0.7rem;
    border-radius: 10px;
    cursor: pointer;
  }
  .start-btn:hover:not(:disabled) {
    background: var(--accent);
    color: var(--bg);
  }
  .start-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
