// Whether a reply came from the response cache, on the Chatter page.
//
// agents7 v4.24.0 made a cache hit report its own numbers instead of
// replaying the stored call's: the lookup's duration, and a cost of
// zero on a priced engine. That is honest but indistinguishable on
// screen from a real call that happened to be fast and free — and
// the token counts shown beside it are the *original* call's, which
// were not billed a second time. So the line has to say so.
//
// The reply and the guard are cached separately, so a turn where
// only the reply was a hit is a turn that half happened. It says
// "reply cached" rather than "cached", because the guard's price is
// on the same line and really was paid.

import { test, expect } from '@playwright/test'
import { stubApi } from './_helpers.js'

const meta = page => page.locator('.bubble.assistant .bubble-tokens')

/**
 * Open the Chatter page and send one message.
 *
 * @param metrics The `metrics` object the done frame carries.
 */
async function sendOneTurn(page, metrics) {
  await stubApi(page)

  await page.route('**/api/chat/start/**', route =>
    route.fulfill({ json: { session_id: 'sess-1', can_open: false } }),
  )
  await page.route('**/api/chat/*/stream', route =>
    route.fulfill({
      contentType: 'text/event-stream',
      body: [
        'data: {"delta": "aquí "}\n\n',
        'data: {"delta": "liado"}\n\n',
        `event: done\ndata: ${JSON.stringify({ metrics })}\n\n`,
      ].join(''),
    }),
  )

  await page.goto('/#/chatter')
  await expect(page.locator('.transcript')).toBeVisible()

  await page.locator('.input-row textarea').fill('hola')
  await page.locator('.input-row textarea').press('Enter')
  await expect(page.locator('.bubble.assistant .bubble-text')).toHaveText(
    'aquí liado',
  )
}

test('a cached turn says so', async ({ page }) => {
  await sendOneTurn(page, {
    tokens: 29,
    prompt_tokens: 6243,
    cached_prompt_tokens: 6243,
    total_duration: 0.0004,
    cost_cents: 0.0,
    cached: true,
  })

  // 0.0s and no price: without the word this is a real call that
  // took no time and was free.
  await expect(meta(page)).toHaveText('29 tok · 0.0s · cached')
})

test('a live turn says nothing about the cache', async ({ page }) => {
  await sendOneTurn(page, {
    tokens: 29,
    total_duration: 1.9,
    cost_cents: 0.0167856,
    cached: false,
  })

  await expect(meta(page)).toHaveText('29 tok · 1.9s · $0.000168')
})

test('a cached reply beside a live guard is only half cached', async ({
  page,
}) => {
  await sendOneTurn(page, {
    tokens: 29,
    total_duration: 0.0004,
    cost_cents: 0.0,
    cached: true,
    guard: { calls: 1, cost_cents: 0.0145936, cached: false },
    total_cost_cents: 0.0145936,
  })

  // The guard's price is real and on the line, so calling the whole
  // turn cached would contradict it.
  await expect(meta(page)).toContainText('reply cached')
})

test('a turn cached on both halves is cached', async ({ page }) => {
  await sendOneTurn(page, {
    tokens: 29,
    total_duration: 0.0008,
    cost_cents: 0.0,
    cached: true,
    guard: { calls: 1, cost_cents: 0.0, cached: true },
  })

  await expect(meta(page)).toHaveText('29 tok · 0.0s · cached')
})
