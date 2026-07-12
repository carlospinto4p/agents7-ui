<script>
  import { onMount } from 'svelte'
  import Sidebar from './components/Sidebar.svelte'
  import Home from './pages/Home.svelte'
  import Catalog from './pages/Catalog.svelte'
  import Classes from './pages/Classes.svelte'
  import Runner from './pages/Runner.svelte'
  import Chatter from './pages/Chatter.svelte'
  import Engine from './pages/Engine.svelte'
  import Eval from './pages/Eval.svelte'

  let page = $state(getPage())
  let ollamaStatus = $state('checking')
  let canStart = $state(false)
  let starting = $state(false)
  let appName = $state('')
  let appVersion = $state('')

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
      canStart = !!data.can_start
    } catch {
      ollamaStatus = 'down'
    }
  }

  async function startOllama() {
    if (starting) return
    starting = true
    try {
      // The endpoint blocks until Ollama is ready (or times out),
      // so a single status refresh afterwards is enough.
      await fetch('/api/engine/start', { method: 'POST' })
      await checkOllama()
    } catch {
      // leave status as-is; the pill keeps polling
    } finally {
      starting = false
    }
  }

  onMount(() => {
    checkOllama()
    const id = setInterval(checkOllama, 30000)
    return () => clearInterval(id)
  })

  $effect(() => {
    fetch('/api/info')
      .then(r => (r.ok ? r.json() : null))
      .then(data => {
        if (data) {
          appName = data.name ?? ''
          appVersion = data.version ?? ''
        }
      })
      .catch(() => {})
  })
</script>

<div class="shell">
  <Sidebar
    {page}
    name={appName}
    version={appVersion}
    {ollamaStatus}
    {canStart}
    {starting}
    onstart={startOllama}
  />
  <main>
    <div class="content">
      {#if page === 'home'}
        <Home />
      {:else if page === 'catalog'}
        <Catalog />
      {:else if page === 'classes'}
        <Classes />
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
    </div>
  </main>
</div>

<style>
  .shell {
    display: flex;
    height: 100vh;
    width: 100%;
    overflow: hidden;
  }
  main {
    flex: 1;
    min-width: 0;
    overflow-y: auto;
  }
  .content {
    padding: 1.5rem;
    width: 100%;
    max-width: 1400px;
    margin: 0 auto;
  }
</style>
