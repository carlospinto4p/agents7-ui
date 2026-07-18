// Tool agents on the Eval page.
//
// A tool agent is scored on its trajectory, so the run carries a
// `trajectory` block instead of a per-category breakdown, and each
// mismatch names the calls made, missed and added rather than an
// expected/actual field dump.

import { test, expect } from '@playwright/test'
import { stubApi } from './_helpers.js'

const TOOL_AGENT = {
  name: 'store_assistant',
  display_name: 'StoreAssistant',
  agent_type: 'tool',
  provider: 'ollama',
  model: 'gemma4:12b',
  version: '1',
  description: 'Answers questions by calling catalog and stock tools.',
}

const TRAJECTORY_RESULT = {
  agent: 'StoreAssistant',
  golden_set: 'eval_data.jsonl',
  total: 4,
  passed: 3,
  failed: 1,
  accuracy: 0.75,
  per_category: {},
  trajectory: {
    mode: 'in_order',
    expected_calls: 8,
    matched_calls: 6,
    extra_calls: 2,
    per_tool: {
      check_stock: { expected: 3, matched: 1 },
      find_product: { expected: 4, matched: 4 },
      order_total: { expected: 1, matched: 1 },
    },
  },
  mismatches: [
    {
      input: 'Are the green ceramic mugs available?',
      expected: { tools: ['find_product(…)', "check_stock(sku='MUG-02')"] },
      actual: { tools: ['find_product(query=\'green mug\')'] },
      passed: false,
      error: null,
      called: ["find_product(query='green mug')"],
      missing: ["check_stock(sku='MUG-02')"],
      extra: [],
    },
  ],
}

// The structured-agent shape, to prove the trajectory view does not
// leak into a normal labeler run.
const FIELD_RESULT = {
  agent: 'tagger_agent',
  golden_set: 'golden_set.csv',
  total: 2,
  passed: 1,
  failed: 1,
  accuracy: 0.5,
  per_category: { FEMALE: { total: 2, passed: 1, accuracy: 0.5 } },
  mismatches: [
    {
      input: { text: 'jessica_2001' },
      expected: { category: 'FEMALE' },
      actual: { category: 'MALE' },
      passed: false,
    },
  ],
}

async function runEval(page, json) {
  await page.route('**/api/eval/**', route => route.fulfill({ json }))
  await page.goto('/#/eval')
  await page.getByRole('button', { name: 'Run Eval' }).click()
}

test('trajectory metrics and per-tool recall are rendered', async ({
  page,
}) => {
  await stubApi(page, { agents: [TOOL_AGENT] })
  await runEval(page, TRAJECTORY_RESULT)

  const summary = page.getByTestId('trajectory-summary')
  await expect(summary).toBeVisible()
  await expect(summary).toContainText('in_order')
  await expect(summary).toContainText('6/8 expected calls made')
  await expect(summary).toContainText('75%')
  await expect(summary).toContainText('2 extra')

  // One row per tool, worst recall first so the weak tool leads.
  const rows = summary.locator('tbody tr')
  await expect(rows).toHaveCount(3)
  await expect(rows.first()).toContainText('check_stock')
  await expect(rows.first()).toContainText('33%')
  await expect(rows.last()).toContainText('100%')
})

test('a failed row names the calls made, missed and added', async ({
  page,
}) => {
  await stubApi(page, { agents: [TOOL_AGENT] })
  await runEval(page, TRAJECTORY_RESULT)

  const mismatch = page.locator('.mismatch').first()
  await expect(mismatch).toContainText('Are the green ceramic mugs available?')
  await expect(mismatch).toContainText('Called')
  await expect(mismatch).toContainText("find_product(query='green mug')")
  await expect(mismatch).toContainText('Missing')
  await expect(mismatch).toContainText("check_stock(sku='MUG-02')")

  // Empty sections are omitted rather than shown as a dash.
  await expect(mismatch).not.toContainText('Extra')
  // The field-scored labels belong to the structured view only.
  await expect(mismatch).not.toContainText('Expected')
})

test('a field-scored agent keeps the per-category view', async ({ page }) => {
  await stubApi(page, { agents: [{ ...TOOL_AGENT, agent_type: 'labeler' }] })
  await runEval(page, FIELD_RESULT)

  await expect(page.getByTestId('trajectory-summary')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Per-category' })).toBeVisible()

  const mismatch = page.locator('.mismatch').first()
  await expect(mismatch).toContainText('Expected')
  await expect(mismatch).toContainText('Actual')
  await expect(mismatch).toContainText('FEMALE')
})
