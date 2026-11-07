// A stubbed read for the Reads page specs.
//
// Shaped like what `/api/reads/detail` returns for a folder of
// recordings with no `read.yml`: conversations and feedback, no
// verdicts or numbers. This file defines no `test()`, so Playwright
// does not collect it as a spec.

import { expect } from '@playwright/test'
import { stubApi } from './_helpers.js'

const PATH = 'demo_agent/docs/reads/2026-09-20'

function turn(i, prompt, messages) {
  return {
    i,
    prompt,
    messages,
    chatter_s: 1.8312,
    guard_s: 1.6049,
    gap_s: 0.0127,
    wall_s: 3.4488,
    chatter_c: 0.021437,
    guard_c: 0.019902,
    running_c: 0.041339 * i,
    prompt_t: 2114,
    out_t: 23,
    cached_pct: 87,
    cached: false,
    retries: 0,
    attempts: 1,
    rejected: 0,
    attempts_detail: [],
    notes: [],
  }
}

export const CONVERSATIONS = [
  {
    id: 'warm',
    title: 'Warm',
    tab: 'Warm',
    tag: 'warm.json',
    note: '',
    context: [{ label: 'nick', value: 'Luna_84' }],
    turns: [
      turn(1, 'y tienes mascota?', ['un gato', 'se llama Pixel']),
      turn(2, 'qué mono', ['es un trasto']),
      turn(3, 'jaja', ['y tú qué, algún bicho en casa?']),
    ],
  },
  {
    id: 'cold',
    title: 'Cold',
    tab: 'Cold',
    tag: 'cold.json',
    note: '',
    context: [],
    turns: [turn(1, 'hola', ['buenas'])],
  },
]

/**
 * Open the Reads page on the first conversation of a stubbed read.
 *
 * @param page    Playwright page.
 * @param entries Feedback entries the read already carries.
 * @returns The body of every feedback save the page made.
 */
export async function openRead(page, entries = []) {
  await stubApi(page)

  let stored = [...entries]
  const saves = []
  const answer = () => ({
    feedback: { entries: stored, golden: [] },
    report: '',
    rule_changes: [],
    eval_rows: 0,
  })

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
            has_feedback: entries.length > 0,
          },
        ],
      },
    }),
  )
  await page.route('**/api/reads/report?**', route =>
    route.fulfill({ json: answer() }),
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
        verdict_kinds: {
          right: 'Right',
          weak: 'Could be better',
          wrong: 'Wrong',
        },
        note_kinds: {},
        conversations: CONVERSATIONS,
        feedback: answer().feedback,
      },
    }),
  )
  await page.route('**/api/reads/feedback?**', route => {
    const body = JSON.parse(route.request().postData() || '{}')
    saves.push(body)
    stored = [...stored, ...(body.entries ?? [])]
    route.fulfill({ json: answer() })
  })

  await page.goto('/#/reads/conv-0')
  await expect(page.locator('.thread')).toBeVisible()
  return saves
}
