// Saving a Chatter conversation as a read.
//
// The step that joins the two halves of the UI. Until this existed a
// conversation held here was answered and forgotten: the Reads page
// could only show what a script had recorded, so feeding back on a
// chat meant leaving the UI and recording it again — and at
// temperature, running it again is a different conversation, so it
// could never be the same one.
//
// The Download button beside it writes `{role, text}`, which no read
// can use: no per-call metrics, no guard verdicts, no context. This
// one writes the recording the Reads page reads.

import { test, expect } from '@playwright/test'
import { stubApi } from './_helpers.js'

const REPLY_SSE = [
  'data: {"delta": "un gato, "}\n\n',
  'data: {"delta": "se llama Pixel"}\n\n',
  'event: done\ndata: {"metrics": {"tokens": 6}}\n\n',
].join('')

const saveButton = page => page.getByTestId('save-read')
const saveNote = page => page.getByTestId('save-read-note')

/**
 * Open the Chatter page with a stubbed session and save endpoint.
 *
 * @param answer How the save endpoint replies.
 * @returns The bodies of every save request the page made.
 */
async function openChatter(page, answer = {}) {
  await stubApi(page)

  const saveCalls = []
  // Registered after stubApi, so these win over the catch-all.
  await page.route('**/api/chat/start/**', route =>
    route.fulfill({ json: { session_id: 'sess-1' } }),
  )
  await page.route('**/api/chat/*/stream', route =>
    route.fulfill({
      contentType: 'text/event-stream',
      body: REPLY_SSE,
    }),
  )
  await page.route('**/api/chat/*/save-read', route => {
    saveCalls.push(JSON.parse(route.request().postData() || '{}'))
    route.fulfill({
      status: answer.status ?? 200,
      json: answer.json ?? {
        path: 'demo_agent/docs/reads/2026-09-20',
        read_id: '2026-09-20',
        conversation_id: 'chat',
        turns: 1,
      },
    })
  })

  await page.goto('/#/chatter')
  await expect(page.locator('.transcript')).toBeVisible()
  return saveCalls
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
  await openChatter(page)

  // Nothing to save, so the toolbar it lives on does not exist.
  await expect(saveButton(page)).toHaveCount(0)
})

test('the control appears once there is a conversation', async ({
  page,
}) => {
  await openChatter(page)
  await sendOne(page)

  await expect(saveButton(page)).toBeVisible()
})

test('nothing is written until asked for', async ({ page }) => {
  const saveCalls = await openChatter(page)
  await sendOne(page)

  await expect(saveButton(page)).toBeVisible()
  expect(saveCalls).toEqual([])
})

test('the form is hidden until the control is clicked', async ({
  page,
}) => {
  await openChatter(page)
  await sendOne(page)

  await expect(page.locator('.save-read')).toHaveCount(0)
  await saveButton(page).click()
  await expect(page.locator('.save-read')).toBeVisible()
})

test('it offers today and a default name', async ({ page }) => {
  await openChatter(page)
  await sendOne(page)
  await saveButton(page).click()

  const today = new Date().toISOString().slice(0, 10)
  await expect(page.locator('.save-read input').first()).toHaveValue(
    today,
  )
  await expect(page.locator('.save-read input').nth(1)).toHaveValue(
    'chat',
  )
})

test('saving sends the names typed and reports where it went', async ({
  page,
}) => {
  const saveCalls = await openChatter(page, {
    json: {
      path: 'demo_agent/docs/reads/2026-09-20',
      read_id: '2026-09-20',
      conversation_id: 'warm',
      turns: 3,
    },
  })
  await sendOne(page)
  await saveButton(page).click()

  await page.locator('.save-read input').nth(1).fill('warm')
  await page.locator('.save-read .tool-btn.primary').click()

  await expect.poll(() => saveCalls.length).toBe(1)
  expect(saveCalls[0].conversation_id).toBe('warm')
  await expect(saveNote(page)).toContainText('Saved 3 turns')
  await expect(saveNote(page)).toContainText(
    'demo_agent/docs/reads/2026-09-20/warm.json',
  )
})

test('the confirmation links to the saved conversation', async ({
  page,
}) => {
  await openChatter(page, {
    json: {
      path: 'demo_agent/docs/reads/2026-09-20',
      read_id: '2026-09-20',
      conversation_id: 'warm',
      turns: 3,
    },
  })
  await sendOne(page)
  await saveButton(page).click()
  await page.locator('.save-read .tool-btn.primary').click()

  // The read by its path and the conversation by its name, which
  // is all the Chatter page knows about what it just wrote.
  await expect(page.getByTestId('open-read')).toHaveAttribute(
    'href',
    '#/reads?read=demo_agent%2Fdocs%2Freads%2F2026-09-20&conv=warm',
  )
})

test('a failed save offers no link', async ({ page }) => {
  await openChatter(page, {
    status: 409,
    json: { detail: '2026-09-20/warm.json already exists.' },
  })
  await sendOne(page)
  await saveButton(page).click()
  await page.locator('.save-read .tool-btn.primary').click()

  await expect(saveNote(page)).toBeVisible()
  await expect(page.getByTestId('open-read')).toHaveCount(0)
})

test('the form closes once it has saved', async ({ page }) => {
  await openChatter(page)
  await sendOne(page)
  await saveButton(page).click()
  await page.locator('.save-read .tool-btn.primary').click()

  await expect(saveNote(page)).toBeVisible()
  await expect(page.locator('.save-read')).toHaveCount(0)
})

test('a name collision is reported, not swallowed', async ({ page }) => {
  // A recording is paid for and is never overwritten, so the
  // backend refuses — and the operator has to see why.
  await openChatter(page, {
    status: 409,
    json: { detail: '2026-09-20/warm.json already exists.' },
  })
  await sendOne(page)
  await saveButton(page).click()
  await page.locator('.save-read .tool-btn.primary').click()

  await expect(saveNote(page)).toHaveText(
    '2026-09-20/warm.json already exists.',
  )
  // Still open, so the name can be changed and tried again.
  await expect(page.locator('.save-read')).toBeVisible()
})

test('an empty name cannot be submitted', async ({ page }) => {
  const saveCalls = await openChatter(page)
  await sendOne(page)
  await saveButton(page).click()

  await page.locator('.save-read input').first().fill('')

  await expect(
    page.locator('.save-read .tool-btn.primary'),
  ).toBeDisabled()
  expect(saveCalls).toEqual([])
})
