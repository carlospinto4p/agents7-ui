// Shared API stubs for the e2e suite.
//
// No backend is started: every boundary the app touches is answered
// here, so each spec is fast and hermetic. This file defines no
// `test()`, so Playwright does not collect it as a spec.
//
// Registration order matters — Playwright matches the MOST RECENTLY
// registered handler first, so the catch-all is registered first and
// the specific endpoints last.

export const AGENT = {
  name: 'test_chatter',
  display_name: 'Test Chatter',
  agent_type: 'chatter',
  provider: 'ollama',
  model: 'qwen2.5:14b',
  version: '1.0.0',
  description: 'An agent used by the e2e suite.',
}

/**
 * Stub every /api boundary the app calls.
 *
 * @param page      Playwright page.
 * @param overrides `agents`, `providers`, `models`, `detail` to vary
 *                  per spec. `detail` is the agent-detail payload the
 *                  Chatter and Catalog pages fetch per agent.
 */
export async function stubApi(page, overrides = {}) {
  const {
    agents = [AGENT],
    providers = [],
    models = [],
    detail = { persona: null, scene: null },
  } = overrides

  // Catch-all first — anything not explicitly stubbed below (chat
  // session start/delete, eval, ...) gets an empty 200 rather than
  // reaching a real backend.
  await page.route('**/api/**', route => route.fulfill({ json: {} }))

  await page.route('**/api/info', route =>
    route.fulfill({ json: { name: 'agents7-ui', version: '0.0.0-test' } }),
  )
  await page.route('**/api/engine/status', route =>
    route.fulfill({ json: { available: true, can_start: false } }),
  )
  await page.route('**/api/engine/models', route =>
    route.fulfill({ json: { models } }),
  )
  await page.route('**/api/chat/providers', route =>
    route.fulfill({ json: { providers } }),
  )
  // Agent detail and the bare list are distinct patterns (the detail
  // route requires a trailing segment), so neither shadows the other.
  await page.route('**/api/catalog/*', route =>
    route.fulfill({ json: detail }),
  )
  await page.route('**/api/catalog', route =>
    route.fulfill({ json: agents }),
  )
}
