<script>
  import { onMount } from 'svelte'
  import Home from './pages/Home.svelte'
  import Catalog from './pages/Catalog.svelte'
  import Runner from './pages/Runner.svelte'
  import Chatter from './pages/Chatter.svelte'
  import Engine from './pages/Engine.svelte'
  import Eval from './pages/Eval.svelte'

  let page = $state(getPage())
  let ollamaStatus = $state('checking')

  function getPage() {
    return window.location.hash.replace('#/', '').split('/')[0] || 'home'
  }

  $effect(() => {
    const onHashChange = () => { page = getPage() }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  })

  async function checkOllama() {
    try {
      const r = await fetch('/api/engine/status')
      const data = await r.json()
      ollamaStatus = data.available ? 'up' : 'down'
    } catch {
      ollamaStatus = 'down'
    }
  }

  onMount(() => {
    checkOllama()
    const id = setInterval(checkOllama, 30000)
    return () => clearInterval(id)
  })
</script>

<header>
  <div class="header-inner">
    <span class="logo">agents7</span>
    <nav>
      <a href="#/home" class:active={page === 'home'}>Home</a>
      <a href="#/catalog" class:active={page === 'catalog'}>Catalog</a>
      <a href="#/runner" class:active={page === 'runner'}>Runner</a>
      <a href="#/chatter" class:active={page === 'chatter'}>Chatter</a>
      <a href="#/engine" class:active={page === 'engine'}>Engine</a>
      <a href="#/eval" class:active={page === 'eval'}>Eval</a>
    </nav>
    <div class="ollama-pill" class:up={ollamaStatus === 'up'} class:down={ollamaStatus === 'down'}>
      <span class="dot"></span>
      <span>Ollama</span>
    </div>
  </div>
</header>

<main>
  {#if page === 'home'}
    <Home />
  {:else if page === 'catalog'}
    <Catalog />
  {:else if page === 'runner'}
    <Runner />
  {:else if page === 'chatter'}
    <Chatter />
  {:else if page === 'engine'}
    <Engine />
  {:else if page === 'eval'}
    <Eval />
  {:else}
    <p>Page not found.</p>
  {/if}
</main>

<style>
  header {
    border-bottom: 1px solid var(--border);
    background: var(--bg-header);
    position: sticky;
    top: 0;
    z-index: 10;
  }
  .header-inner {
    display: flex;
    align-items: center;
    gap: 2rem;
    padding: 0.75rem 1.5rem;
    max-width: 1400px;
    margin: 0 auto;
    width: 100%;
  }
  .logo {
    font-weight: 700;
    font-size: 1.1rem;
    letter-spacing: -0.5px;
    color: var(--text-strong);
  }
  nav {
    display: flex;
    gap: 1.25rem;
  }
  nav a {
    text-decoration: none;
    color: var(--text-muted);
    font-size: 0.95rem;
  }
  nav a.active {
    color: var(--accent);
    font-weight: 600;
  }
  .ollama-pill {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.78rem;
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
  main {
    flex: 1;
    padding: 1.5rem;
    width: 100%;
    max-width: 1400px;
    margin: 0 auto;
  }
</style>
