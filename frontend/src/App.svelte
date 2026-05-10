<script>
  import Catalog from './pages/Catalog.svelte'
  import Runner from './pages/Runner.svelte'
  import Engine from './pages/Engine.svelte'
  import Eval from './pages/Eval.svelte'

  let page = $state(getPage())

  function getPage() {
    return window.location.hash.replace('#/', '').split('/')[0] || 'catalog'
  }

  $effect(() => {
    const onHashChange = () => { page = getPage() }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  })
</script>

<header>
  <span class="logo">agents7</span>
  <nav>
    <a href="#/catalog" class:active={page === 'catalog'}>Catalog</a>
    <a href="#/runner" class:active={page === 'runner'}>Runner</a>
    <a href="#/engine" class:active={page === 'engine'}>Engine</a>
    <a href="#/eval" class:active={page === 'eval'}>Eval</a>
  </nav>
</header>

<main>
  {#if page === 'catalog'}
    <Catalog />
  {:else if page === 'runner'}
    <Runner />
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
    display: flex;
    align-items: center;
    gap: 2rem;
    padding: 0.75rem 1.5rem;
    border-bottom: 1px solid var(--border);
    background: var(--bg-header);
    position: sticky;
    top: 0;
    z-index: 10;
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
  main {
    flex: 1;
    padding: 1.5rem;
  }
</style>
