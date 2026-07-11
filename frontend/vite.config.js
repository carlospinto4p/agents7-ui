import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig({
  plugins: [svelte()],
  server: {
    // Registry-claimed dev port — never the shared Vite default (5173).
    port: 5186,
    proxy: {
      '/api': 'http://localhost:8002',
    },
  },
})
