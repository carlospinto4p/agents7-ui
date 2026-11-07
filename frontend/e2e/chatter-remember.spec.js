// Recording character facts from the Chatter page.
//
// An agent whose config declares a `character_facts` store can write
// down what it said about itself, so a later conversation still knows
// it. The start response reports that as `can_remember`, and the page
// offers a control that asks for it.
//
// The control is a click and never automatic: the session is torn
// down and restarted on every agent, provider, model and context
// change, so anything wired to teardown would spend an LLM call on a
// dropdown fiddle. An agent with no store gets no control, since the
// backend would reject the call with a 422.

import { test, expect } from '@playwright/test'
import { stubApi } from './_helpers.js'

const REPLY_SSE = [
  'data: {"delta": "un gato, "}\n\n',
  'data: {"delta": "se llama Pixel"}\n\n',
  'event: done\ndata: {"metrics": {"tokens": 6}}\n\n',
].join('')

const rememberButton = page => page.getByTestId('remember-facts')
const rememberNote = page => page.getByTestId('remember-note')

/**
 * Open the Chatter page with a stubbed chat session.
 *
 * @param canRemember Whether the started session reports a fact store.
 * @param facts       What the remember endpoint answers with.
 * @returns The URLs of every remember request the page made.
 */
async function openChatter(page, canRemember, facts = []) {
  await stubApi(page)

  const rememberCalls = []
  // Registered after stubApi, so these win over the catch-all.
  await page.route('**/api/chat/start/**', route =>
    route.fulfill({
      json: { session_id: 'sess-1', can_remember: canRemember },
    }),
  )
  await page.route('**/api/chat/*/stream', route =>
    route.fulfill({
      contentType: 'text/event-stream',
      body: REPLY_SSE,
    }),
  )
  await page.route('**/api/chat/*/remember', route => {
    rememberCalls.push(route.request().url())
    route.fulfill({ json: { facts } })
  })

  await page.goto('/#/chatter')
  await expect(page.locator('.transcript')).toBeVisible()
  return rememberCalls
}

/** Send one message so the transcript is no longer empty. */
async function sendOne(page) {
  await page.locator('.input-row textarea').fill('y tienes mascota?')
  await page.locator('.send-btn').click()
  await expect(
    page.locator('.bubble.assistant .bubble-text'),
  ).toHaveText('un gato, se llama Pixel')
}

test('no control before anything has been said', async ({ page }) => {
  await openChatter(page, true)

  // The toolbar only exists once there is a transcript to act on.
  await expect(rememberButton(page)).toHaveCount(0)
})

test('an agent with a fact store offers the control', async ({ page }) => {
  await openChatter(page, true)
  await sendOne(page)

  await expect(rememberButton(page)).toBeVisible()
})

test('an agent with no fact store shows no control', async ({ page }) => {
  await openChatter(page, false)
  await sendOne(page)

  // The transcript is there, so the toolbar is too — but only the
  // download button belongs on it for this agent.
  await expect(page.locator('.chat-toolbar')).toBeVisible()
  await expect(rememberButton(page)).toHaveCount(0)
})

test('nothing is recorded until asked for', async ({ page }) => {
  const rememberCalls = await openChatter(page, true, ['Tiene un gato'])
  await sendOne(page)

  await expect(rememberButton(page)).toBeVisible()
  expect(rememberCalls).toEqual([])
  await expect(rememberNote(page)).toHaveCount(0)
})

test('clicking it reports what was written down', async ({ page }) => {
  const rememberCalls = await openChatter(page, true, [
    'Tiene un gato que se llama Pixel',
    'No ve la tele',
  ])
  await sendOne(page)

  await rememberButton(page).click()

  await expect(rememberNote(page)).toHaveText(
    'Recorded: Tiene un gato que se llama Pixel · No ve la tele',
  )
  await expect.poll(() => rememberCalls.length).toBe(1)
})

test('an empty result says so instead of looking broken', async ({
  page,
}) => {
  await openChatter(page, true, [])
  await sendOne(page)

  await rememberButton(page).click()

  // A conversation carrying nothing new is a normal outcome.
  await expect(rememberNote(page)).toHaveText('Nothing new to record.')
  await expect(page.locator('.err-msg')).toHaveCount(0)
})

test('a rejected request surfaces the reason', async ({ page }) => {
  await stubApi(page)
  await page.route('**/api/chat/start/**', route =>
    route.fulfill({ json: { session_id: 'sess-1', can_remember: true } }),
  )
  await page.route('**/api/chat/*/stream', route =>
    route.fulfill({ contentType: 'text/event-stream', body: REPLY_SSE }),
  )
  await page.route('**/api/chat/*/remember', route =>
    route.fulfill({
      status: 422,
      json: { detail: 'This agent does not record character facts.' },
    }),
  )

  await page.goto('/#/chatter')
  await expect(page.locator('.transcript')).toBeVisible()
  await sendOne(page)

  await rememberButton(page).click()

  await expect(page.locator('.err-msg')).toHaveText(
    'This agent does not record character facts.',
  )
  await expect(rememberNote(page)).toHaveCount(0)
})
