<script>
  let status = $state('checking...')

  async function checkHealth() {
    try {
      const res = await fetch('/api/health')
      const data = await res.json()
      status = data.status
    } catch {
      status = 'backend unreachable'
    }
  }

  checkHealth()
</script>

<h1>agents7 UI</h1>
<p>Backend: {status}</p>
