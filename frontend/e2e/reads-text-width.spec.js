// The read's prose is as wide as the cards beside it.
//
// The standfirst, the caveat and the closing each carried
// `max-width: 68ch` while the tabs and the verdict cards ran the full
// column, so on a wide window the text stopped at half the page and
// left the rest blank. A width limit belongs on the page container,
// never on a text block inside it.

import { test, expect } from '@playwright/test'
import { stubApi } from './_helpers.js'
import { CONVERSATIONS } from './_reads.js'

const PATH = 'demo_agent/docs/reads/2026-09-20'

// Long enough to wrap, so a width limit shows as a narrower box.
const PROSE = 'A sentence about the read that goes on for a while. '.repeat(8)

test.use({ viewport: { width: 1920, height: 1080 } })

async function stubRead(page) {
  await stubApi(page)

  const feedback = { entries: [], golden: [] }
  // Registered after stubApi, so these win over the catch-all.
  await page.route('**/api/reads', route =>
    route.fulfill({
      json: {
        reads: [
          {
            path: PATH,
            agent: 'demo_agent',
            agent_version: '1.0.0',
            id: '2026-09-20',
            conversations: CONVERSATIONS.length,
            has_feedback: false,
          },
        ],
      },
    }),
  )
  await page.route('**/api/reads/report?**', route =>
    route.fulfill({
      json: { feedback, report: '', rule_changes: [], eval_rows: 0 },
    }),
  )
  await page.route('**/api/reads/detail?**', route =>
    route.fulfill({
      json: {
        path: PATH,
        read_id: '2026-09-20',
        title: 'demo_agent 2026-09-20',
        has_read_spec: true,
        standfirst: PROSE,
        caveat: PROSE,
        verdicts: [
          { claim: 'A claim', stamp: 'pass', label: 'Holds', detail: PROSE },
        ],
        closing: [PROSE],
        measures: {},
        verdict_kinds: {},
        note_kinds: {},
        conversations: CONVERSATIONS,
        feedback,
      },
    }),
  )
}

const width = async locator => (await locator.boundingBox()).width

test('the read prose fills the column the cards fill', async ({ page }) => {
  await stubRead(page)
  await page.goto('/#/reads/verdicts')

  const card = page.locator('.verdict').first()
  await expect(card).toBeVisible()
  const full = await width(card)

  for (const block of ['.standfirst', '.caveat', '.closing']) {
    expect(
      Math.abs((await width(page.locator(block))) - full),
      `${block} is as wide as a verdict card`,
    ).toBeLessThanOrEqual(1)
  }
})
