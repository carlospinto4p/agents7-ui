// What a turn cost, under the agent's reply on the Chatter page.
//
// Two things were wrong before, and both made the number a lie rather
// than merely imprecise.
//
// A guarded reply is at least two LLM calls — the chatter writes, the
// guard reads it and votes — and only the first is in the reply's own
// metrics. The line showed that figure alone, so a guarded turn read
// at about half its real price with nothing to say a half was missing.
//
// And the cost was formatted to a fixed four decimal places of
// dollars. A guarded chat turn costs a few hundredths of a cent, so a
// real $0.000168 rounded to "$0.0002" and anything under $0.00005
// rounded to "$0.0000" — a price that reads as free.
//
// The figures below are those of a real guarded turn against DeepSeek.

import { test, expect } from '@playwright/test'
import { stubApi } from './_helpers.js'

const CHATTER_COST = 0.0167856
const GUARD_COST = 0.0145936
const TURN_COST = CHATTER_COST + GUARD_COST

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

test('a guarded turn shows both halves and the total', async ({ page }) => {
  await sendOneTurn(page, {
    tokens: 29,
    prompt_tokens: 6243,
    total_duration: 1.9,
    cost_cents: CHATTER_COST,
    guard: { calls: 1, cost_cents: GUARD_COST },
    total_cost_cents: TURN_COST,
  })

  // The guard is about half the bill, so hiding it halved the price.
  await expect(meta(page)).toHaveText(
    '29 tok · 1.9s · $0.000168 + guard $0.000146 = $0.000314',
  )
})

test('a small cost is not rounded away to zero', async ({ page }) => {
  await sendOneTurn(page, {
    tokens: 12,
    total_duration: 0.8,
    cost_cents: 0.0045,
  })

  // The old formatter rendered this exact turn as "$0.0000".
  // Asserted on the whole line, because "$0.000045" contains
  // "$0.0000" as a substring — a `not.toContainText` here passes
  // for the wrong reason and would not have caught the bug.
  await expect(meta(page)).toHaveText('12 tok · 0.8s · $0.000045')
})

test('an unguarded turn shows one cost and no total', async ({ page }) => {
  await sendOneTurn(page, {
    tokens: 12,
    total_duration: 0.8,
    cost_cents: 1.0,
  })

  await expect(meta(page)).toHaveText('12 tok · 0.8s · $0.01')
})

test('a local model reports no cost and the line omits it', async ({
  page,
}) => {
  await sendOneTurn(page, {
    tokens: 12,
    total_duration: 0.8,
    cost_cents: null,
  })

  // Ollama is free, so there is no price to show — and a missing
  // price must never render as $0.00, which reads as measured.
  await expect(meta(page)).toHaveText('12 tok · 0.8s')
  await expect(meta(page)).not.toContainText('$')
})
