// A failed turn on the Chatter page.
//
// Once a streaming response has started, the backend can no longer
// report a failure as an HTTP status — the status line is already
// sent. So `_stream_turn` in `backend/routers/chat.py` catches the
// failure and writes one `event: error` frame into the stream
// instead, and `ChatPanel.svelte` renders its `error` field above the
// transcript.
//
// v0.33.3 widened that catch to every provider error, so the frame is
// now the way most failures reach the user rather than an edge case.
// These specs push the frame over the stubbed stream and check what
// the page does with it.

import { test, expect } from '@playwright/test'
import { stubApi } from './_helpers.js'

// The frame the backend writes when a turn fails before any token.
const ERROR_SSE = 'event: error\ndata: {"error": "Internal chat error"}\n\n'

// A turn that produced text and then failed. The tokens already sent
// are not taken back.
const PARTIAL_THEN_ERROR_SSE = [
  'data: {"delta": "Pues mira, "}\n\n',
  'event: error\ndata: {"error": "Internal chat error"}\n\n',
].join('')

// A well-formed error frame carrying no message.
const BARE_ERROR_SSE = 'event: error\ndata: {}\n\n'

const OK_SSE = [
  'data: {"delta": "ahora sí"}\n\n',
  'event: done\ndata: {"metrics": {"tokens": 3}}\n\n',
].join('')

const errMsg = page => page.locator('.err-msg')
const bubbleText = page => page.locator('.bubble.assistant .bubble-text')

/**
 * Open the Chatter page with a stubbed chat session.
 *
 * @param bodies  What each successive reply request answers with. The
 *                last entry is repeated once the list runs out, so a
 *                single-entry list answers every turn the same way.
 * @param canOpen Whether the started session reports that the agent
 *                may speak first.
 * @param opening What an opening-turn request answers with.
 */
async function openChatter(page, bodies, canOpen = false, opening = OK_SSE) {
  await stubApi(page)

  let turn = 0
  // Registered after stubApi, so these win over the catch-all.
  await page.route('**/api/chat/start/**', route =>
    route.fulfill({ json: { session_id: 'sess-1', can_open: canOpen } }),
  )
  await page.route('**/api/chat/*/stream', route => {
    const body = bodies[Math.min(turn, bodies.length - 1)]
    turn += 1
    route.fulfill({ contentType: 'text/event-stream', body })
  })
  await page.route('**/api/chat/*/open/stream', route =>
    route.fulfill({ contentType: 'text/event-stream', body: opening }),
  )

  await page.goto('/#/chatter')
  await expect(page.locator('.transcript')).toBeVisible()
}

/** Send one message, whatever the stubbed stream answers with. */
async function send(page, text) {
  await page.locator('.input-row textarea').fill(text)
  await page.locator('.send-btn').click()
}

test('a failed turn says so above the transcript', async ({ page }) => {
  await openChatter(page, [ERROR_SSE])

  await send(page, 'y tienes mascota?')

  await expect(errMsg(page)).toHaveText('Internal chat error')
})

test('a turn that failed before speaking leaves no empty bubble', async ({
  page,
}) => {
  await openChatter(page, [ERROR_SSE])

  await send(page, 'y tienes mascota?')
  await expect(errMsg(page)).toBeVisible()

  // The bubble is opened optimistically when the turn starts and
  // dropped again when nothing arrives, so no placeholder is left
  // sitting in the transcript pretending the agent is still typing.
  await expect(bubbleText(page)).toHaveCount(0)
  // What the user typed stays: only the agent's turn failed.
  await expect(page.locator('.bubble.user .bubble-text')).toHaveText(
    'y tienes mascota?',
  )
})

test('a turn that failed mid-sentence keeps what arrived', async ({
  page,
}) => {
  await openChatter(page, [PARTIAL_THEN_ERROR_SSE])

  await send(page, 'y tienes mascota?')

  await expect(errMsg(page)).toHaveText('Internal chat error')
  await expect(bubbleText(page)).toHaveText('Pues mira,')
})

test('an error frame with no message still reports one', async ({
  page,
}) => {
  await openChatter(page, [BARE_ERROR_SSE])

  await send(page, 'y tienes mascota?')

  await expect(errMsg(page)).toHaveText('Chat error')
})

test('the opening turn reports a failure the same way', async ({ page }) => {
  await openChatter(page, [OK_SSE], true, ERROR_SSE)

  await page.getByTestId('open-turn').click()

  await expect(errMsg(page)).toHaveText('Internal chat error')
  await expect(bubbleText(page)).toHaveCount(0)
})

test('the next message clears the previous failure', async ({ page }) => {
  await openChatter(page, [ERROR_SSE, OK_SSE])

  await send(page, 'y tienes mascota?')
  await expect(errMsg(page)).toBeVisible()

  await send(page, 'perdona, otra vez')

  await expect(bubbleText(page)).toHaveText('ahora sí')
  await expect(errMsg(page)).toHaveCount(0)
})
