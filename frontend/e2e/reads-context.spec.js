// The block above a conversation that says what it ran with.
//
// It was one grid of 300px columns holding every row, so the list of
// facts the agent already knew wrapped into a tall strip a quarter of
// the width, with the space under the other columns empty. The rows
// now sit in one section per group the framework names, a long value
// takes its section's whole width, and the facts are a list.

import { test, expect } from '@playwright/test'
import { stubApi } from './_helpers.js'
import { CONVERSATIONS } from './_reads.js'

const PATH = 'demo_agent/docs/reads/2026-09-20'

const FACTS = [
  'Vive en Lavapiés.',
  'Trabaja en una librería del centro.',
  'Le gusta el cine clásico.',
  'Tiene un perro que se llama Toby.',
]

const LONG = 'Quiere hablar de la exposición de fotografía que vio el sábado.'

const GROUPED = [
  { label: 'When', value: '2 October 2026, 18:55 UTC', group: 'run' },
  { label: 'Agent', value: 'demo_agent v1.0.0', group: 'run' },
  { label: 'nick', value: 'Marta_87', group: 'context' },
  { label: 'tema', value: LONG, group: 'context' },
  {
    label: 'Knew already',
    value: FACTS.join(' · '),
    items: FACTS,
    group: 'memory',
  },
  { label: 'variant: bien_reply', value: 'un bien', group: 'variants' },
]

test.use({ viewport: { width: 1920, height: 1080 } })

async function openWith(page, context) {
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
            conversations: 1,
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
        has_read_spec: false,
        verdicts: [],
        measures: {},
        verdict_kinds: {},
        note_kinds: {},
        conversations: [{ ...CONVERSATIONS[0], context }],
        feedback,
      },
    }),
  )

  await page.goto('/#/reads/conv-0')
  await expect(page.locator('.ctx')).toBeVisible()
}

const width = async locator => (await locator.boundingBox()).width

test('the rows sit in one titled section per group', async ({ page }) => {
  await openWith(page, GROUPED)

  await expect(page.locator('.ctx-title')).toHaveText([
    'Run',
    'Context',
    'Knew already',
    'Variants',
  ])
  await expect(
    page.locator('[data-group="run"] .ctx-row'),
  ).toHaveCount(2)
  await expect(
    page.locator('[data-group="variants"] dt'),
  ).toHaveText('bien_reply')
})

test('the facts are a list across the section, not a strip', async ({
  page,
}) => {
  await openWith(page, GROUPED)

  const items = page.locator('[data-group="memory"] .ctx-items li')
  await expect(items).toHaveText(FACTS)

  // More than one column: two facts share a row.
  const tops = await items.evaluateAll(els =>
    els.map(el => Math.round(el.getBoundingClientRect().top)),
  )
  expect(new Set(tops).size).toBeLessThan(FACTS.length)
})

test('a long value takes the whole width of its section', async ({
  page,
}) => {
  await openWith(page, GROUPED)

  const body = page.locator('[data-group="context"] .ctx-body')
  const long = body.locator('.ctx-row', { hasText: 'tema' })
  const short = body.locator('.ctx-row', { hasText: 'Marta_87' })

  expect(
    Math.abs((await width(long)) - (await width(body))),
  ).toBeLessThanOrEqual(1)
  expect(await width(short)).toBeLessThan((await width(body)) / 2)
})

test('rows with no group still show, in one untitled section', async ({
  page,
}) => {
  await openWith(page, [{ label: 'nick', value: 'Luna_84' }])

  await expect(page.locator('.ctx-title')).toHaveCount(0)
  await expect(page.locator('.ctx-row dt')).toHaveText('nick')
  await expect(page.locator('.ctx-row dd')).toHaveText('Luna_84')
})
