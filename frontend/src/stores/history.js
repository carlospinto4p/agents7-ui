import { writable } from 'svelte/store'

const MAX_HISTORY = 50
const KEY = 'agents7_run_history'

function load() {
  try { return JSON.parse(localStorage.getItem(KEY) ?? '[]') } catch { return [] }
}

function save(items) {
  try { localStorage.setItem(KEY, JSON.stringify(items)) } catch {}
}

const { subscribe, update } = writable(load())

export const history = {
  subscribe,
  add(entry) {
    update(items => {
      const next = [entry, ...items].slice(0, MAX_HISTORY)
      save(next)
      return next
    })
  },
  clear() {
    update(() => {
      try { localStorage.removeItem(KEY) } catch {}
      return []
    })
  },
}
