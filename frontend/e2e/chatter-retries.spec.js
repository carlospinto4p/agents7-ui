// Whether a turn had to be retried, on the Chatter page.
//
// agents7 v4.26.0 counts the provider calls that failed and were
// retried, and the seconds they took. On this page those seconds
// are NOT in the duration shown beside them: `total_duration` is
// the successful attempt's own figure, so a turn that spent four
// seconds on backoff still renders as "1.9s". Without the retry
// part, a run fighting rate limits looks exactly like one that
// sailed through, and the wait the user actually sat through is
// nowhere on screen.
//
// A failed attempt raises before the provider reports anything, so
// it has no tokens and no price of its own — the seconds are the
// whole of what it cost, which is why they are shown and no cost is.

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

test('a retried turn says how many and how long', async ({ page }) => {
  await sendOneTurn(page, {
    tokens: 29,
    total_duration: 1.9,
    cost_cents: 0.0167856,
    retries: 2,
    retry_duration: 4.5,
  })

  // 1.9s is the attempt that worked; the 4.5s is the two that did
  // not, and the user waited 6.4s in total.
  await expect(meta(page)).toHaveText(
    '29 tok · 1.9s · $0.000168 · 2 retries (4.5s)',
  )
})

test('one retry is singular', async ({ page }) => {
  await sendOneTurn(page, {
    tokens: 29,
    total_duration: 1.9,
    retries: 1,
    retry_duration: 1.0,
  })

  await expect(meta(page)).toHaveText('29 tok · 1.9s · 1 retry (1.0s)')
})

test('a clean turn says nothing about retries', async ({ page }) => {
  await sendOneTurn(page, {
    tokens: 29,
    total_duration: 1.9,
    cost_cents: 0.0167856,
    retries: 0,
    retry_duration: 0.0,
  })

  await expect(meta(page)).toHaveText('29 tok · 1.9s · $0.000168')
})

test("the guard's retries are counted with the reply's", async ({ page }) => {
  await sendOneTurn(page, {
    tokens: 29,
    total_duration: 1.9,
    cost_cents: 0.0167856,
    retries: 1,
    retry_duration: 2.0,
    guard: {
      calls: 1,
      cost_cents: 0.0145936,
      retries: 2,
      retry_duration: 3.0,
    },
    total_cost_cents: 0.0313792,
  })

  // Both halves held the same person up, so they add.
  await expect(meta(page)).toContainText('3 retries (5.0s)')
})
