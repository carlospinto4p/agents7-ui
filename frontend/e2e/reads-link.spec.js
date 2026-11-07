// Linking to a read.
//
// The Reads page used to open on the first read in its list and
// nothing else, so a read could be reached only by picking it from
// the dropdown. The hash now names the read (`?read=<path>`) and,
// optionally, one of its conversations by id (`&conv=<id>`) — which
// is what lets the Chatter page link to the conversation it just
// saved.

import { test, expect } from '@playwright/test'
import { stubApi } from './_helpers.js'
import { CONVERSATIONS } from './_reads.js'

const NEWER = 'demo_agent/docs/reads/2026-09-20'
const OLDER = 'demo_agent/docs/reads/2026-09-06'

const select = page => page.locator('#read-select')
const activeTab = page => page.locator('.tabs button.on')

/** Stub two reads; each detail request answers for the path asked. */
async function stubReads(page) {
  await stubApi(page)

  const feedback = { entries: [], golden: [] }
  // Registered after stubApi, so these win over the catch-all.
  await page.route('**/api/reads', route =>
    route.fulfill({
      json: {
        reads: [NEWER, OLDER].map(path => ({
          path,
          agent: 'demo_agent',
          agent_version: '1.0.0',
          id: path.split('/').pop(),
          conversations: CONVERSATIONS.length,
          has_feedback: false,
        })),
      },
    }),
  )
  await page.route('**/api/reads/report?**', route =>
    route.fulfill({
      json: { feedback, report: '', rule_changes: [], eval_rows: 0 },
    }),
  )
  await page.route('**/api/reads/detail?**', route => {
    const path = new URL(route.request().url()).searchParams.get('path')
    route.fulfill({
      json: {
        path,
        read_id: path.split('/').pop(),
        title: `demo_agent ${path.split('/').pop()}`,
        has_read_spec: false,
        verdicts: [],
        measures: {},
        verdict_kinds: {},
        note_kinds: {},
        conversations: CONVERSATIONS,
        feedback,
      },
    })
  })
}

test('with no read named it opens the first one', async ({ page }) => {
  await stubReads(page)
  await page.goto('/#/reads')

  await expect(select(page)).toHaveValue(NEWER)
  await expect(activeTab(page)).toHaveText('Warm')
})

test('a link opens the read it names', async ({ page }) => {
  await stubReads(page)
  await page.goto(`/#/reads?read=${encodeURIComponent(OLDER)}`)

  await expect(select(page)).toHaveValue(OLDER)
  await expect(page.locator('h1')).toHaveText('demo_agent 2026-09-06')
})

test('a link opens the conversation it names', async ({ page }) => {
  await stubReads(page)
  await page.goto(
    `/#/reads?read=${encodeURIComponent(OLDER)}&conv=cold`,
  )

  await expect(select(page)).toHaveValue(OLDER)
  await expect(activeTab(page)).toHaveText('Cold')
})

test('a read that does not exist falls back to the first', async ({
  page,
}) => {
  await stubReads(page)
  await page.goto('/#/reads?read=demo_agent%2Fdocs%2Freads%2Fgone')

  await expect(select(page)).toHaveValue(NEWER)
})

test('the address keeps naming the read as tabs change', async ({
  page,
}) => {
  await stubReads(page)
  await page.goto(`/#/reads?read=${encodeURIComponent(OLDER)}`)
  await page.locator('.tabs button', { hasText: 'Cold' }).click()

  // So the address bar can be copied at any point and still lands
  // on this read and this conversation.
  await expect(page).toHaveURL(
    new RegExp(`#/reads/conv-1\\?read=${encodeURIComponent(OLDER)}$`),
  )
})

test('choosing another read is not pulled back by the link', async ({
  page,
}) => {
  await stubReads(page)
  await page.goto(
    `/#/reads?read=${encodeURIComponent(OLDER)}&conv=cold`,
  )
  await expect(activeTab(page)).toHaveText('Cold')

  await select(page).selectOption(NEWER)

  await expect(page.locator('h1')).toHaveText('demo_agent 2026-09-20')
  await expect(page).toHaveURL(
    new RegExp(`read=${encodeURIComponent(NEWER)}$`),
  )
})
