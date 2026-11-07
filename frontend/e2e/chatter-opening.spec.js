// The agent speaking first on the Chatter page.
//
// An agent whose config sets `can_open` may write the opening line of
// a conversation, with nothing to answer. The start response reports
// that as `can_open`, and the page offers a control that asks for the
// opening turn — streamed into the transcript like any other reply.
//
// An agent without it gets no control at all: there is nothing for it
// to open with, and the backend would reject the call.

import { test, expect } from '@playwright/test'
import { stubApi, AGENT } from './_helpers.js'

const OPENING_SSE = [
  'data: {"delta": "¿Qué tal "}\n\n',
  'data: {"delta": "la tarde?"}\n\n',
  'event: done\ndata: {"metrics": {"tokens": 7}}\n\n',
].join('')

const openButton = page => page.getByTestId('open-turn')
const bubbleText = page => page.locator('.bubble.assistant .bubble-text')

/**
 * Open the Chatter page with a stubbed chat session.
 *
 * @param canOpen Whether the started session reports that the agent
 *                may speak first.
 * @returns The URLs of every opening-turn request the page made.
 */
async function openChatter(page, canOpen) {
  await stubApi(page)

  const openCalls = []
  // Registered after stubApi, so these win over the catch-all.
  await page.route('**/api/chat/start/**', route =>
    route.fulfill({ json: { session_id: 'sess-1', can_open: canOpen } }),
  )
  await page.route('**/api/chat/*/open/stream', route => {
    openCalls.push(route.request().url())
    route.fulfill({
      contentType: 'text/event-stream',
      body: OPENING_SSE,
    })
  })

  await page.goto('/#/chatter')
  await expect(page.locator('.transcript')).toBeVisible()
  return openCalls
}

test('an agent that may open offers the control', async ({ page }) => {
  await openChatter(page, true)

  await expect(openButton(page)).toBeVisible()
  await expect(openButton(page)).toHaveText(`Let ${AGENT.name} open`)
})

test('an agent that may not open shows no control', async ({ page }) => {
  await openChatter(page, false)

  await expect(page.locator('.transcript')).toContainText(
    'Session started',
  )
  await expect(openButton(page)).toHaveCount(0)
})

test('the opening turn is not taken until asked for', async ({ page }) => {
  const openCalls = await openChatter(page, true)

  // Starting a session must not spend a model call on its own — the
  // session restarts on every agent, engine and context change.
  await expect(openButton(page)).toBeVisible()
  expect(openCalls).toEqual([])
  await expect(bubbleText(page)).toHaveCount(0)
})

test('clicking it puts the agent line first in the transcript', async ({
  page,
}) => {
  const openCalls = await openChatter(page, true)

  await openButton(page).click()

  await expect(bubbleText(page)).toHaveText('¿Qué tal la tarde?')
  await expect.poll(() => openCalls.length).toBe(1)

  // Nothing the user typed precedes it: the agent speaks first.
  await expect(page.locator('.bubble.user')).toHaveCount(0)
  await expect(page.locator('.bubble').first()).toHaveClass(
    /assistant/,
  )
})

test('the control goes once the agent has spoken', async ({ page }) => {
  await openChatter(page, true)

  await openButton(page).click()
  await expect(bubbleText(page)).toHaveText('¿Qué tal la tarde?')

  // One opening per conversation — the transcript is no longer empty.
  await expect(openButton(page)).toHaveCount(0)
})

test('opening clears the seeded example message', async ({ page }) => {
  await openChatter(page, true)

  const box = page.locator('.input-row textarea')
  // The panel seeds a ready-to-send example on start.
  await expect(box).not.toHaveValue('')

  await openButton(page).click()
  await expect(bubbleText(page)).toHaveText('¿Qué tal la tarde?')

  // That example answers a question the agent has not asked, so the
  // reply is left for the user to write.
  await expect(box).toHaveValue('')
})
