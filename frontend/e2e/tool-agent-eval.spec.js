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
    failed_calls: 1,
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
// leak into a normal labeler run. Since the endpoint routes every
// agent type through `run_eval_suite`, a field-scored run now also
// carries per-field accuracy, timing, the call totals, and an
// `error` that separates a failed call from a wrong answer.
const FIELD_RESULT = {
  agent: 'my_tagger',
  model: 'ollama::gemma4:12b',
  golden_set: 'golden_set.csv',
  fields: ['category', 'reason'],
  total: 3,
  passed: 1,
  failed: 2,
  accuracy: 0.3333,
  per_field: { category: 0.6667, reason: 0.3333 },
  per_category: { FEMALE: { total: 3, passed: 1, accuracy: 0.3333 } },
  timing: {
    total_s: 6.0,
    avg_s: 2.0,
    min_s: 1.5,
    max_s: 2.5,
    per_case: [1.5, 2.0, 2.5],
  },
  trajectory: null,
  calls: {
    calls: 3,
    successes: 2,
    failures: 1,
    tokens: 120,
    prompt_tokens: 880,
    cached_prompt_tokens: 800,
    total_duration: 6.0,
    avg_duration: 2.0,
    cost_cents: 0.0125,
    cached_calls: 1,
    retries: 1,
    retry_duration: 2.0,
    retried_calls: 1,
    success_rate: 0.6667,
  },
  mismatches: [
    {
      input: { text: 'jessica_2001' },
      expected: { category: 'FEMALE' },
      actual: { category: 'MALE' },
      passed: false,
      error: null,
      fields: { category: false },
    },
    {
      input: { text: 'nachete77' },
      expected: { category: 'FEMALE' },
      actual: null,
      passed: false,
      error: 'Connection refused',
      fields: {},
    },
  ],
}

// The same run on a local model and a rule-based agent: nothing to
// price, and no LLM call to summarise.
const UNPRICED_RESULT = {
  ...FIELD_RESULT,
  calls: { ...FIELD_RESULT.calls, cost_cents: null },
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
  // Calls the tools threw out. Without this the run reports a
  // matched/expected gap with nothing saying what closed it.
  await expect(summary).toContainText('1 rejected')

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

test('per-field accuracy is listed worst first', async ({ page }) => {
  await stubApi(page, { agents: [{ ...TOOL_AGENT, agent_type: 'labeler' }] })
  await runEval(page, FIELD_RESULT)

  const section = page.getByTestId('per-field')
  await expect(section).toBeVisible()

  const rows = section.locator('tbody tr')
  await expect(rows).toHaveCount(2)
  await expect(rows.first()).toContainText('reason')
  await expect(rows.first()).toContainText('33%')
  await expect(rows.last()).toContainText('category')
  await expect(rows.last()).toContainText('67%')
})

test('the run reports its calls, time and cost', async ({ page }) => {
  await stubApi(page, { agents: [{ ...TOOL_AGENT, agent_type: 'labeler' }] })
  await runEval(page, FIELD_RESULT)

  const calls = page.getByTestId('eval-calls')
  await expect(calls).toContainText('3 calls')
  await expect(calls).toContainText('1,000 tok')
  // Several calls, so the average and the spread are worth showing.
  await expect(calls).toContainText('6.0s (2.0s avg, 1.5–2.5s)')
  await expect(calls).toContainText('$0.000125')
  await expect(calls).toContainText('1 cached')
  await expect(calls).toContainText('1 retry (2.0s)')
})

test('a single-call run shows no average or spread', async ({ page }) => {
  await stubApi(page, { agents: [{ ...TOOL_AGENT, agent_type: 'labeler' }] })
  // A batched run answers every row in one call, so there is
  // nothing to average and no two calls to compare.
  await runEval(page, {
    ...FIELD_RESULT,
    calls: { ...FIELD_RESULT.calls, calls: 1 },
  })

  const calls = page.getByTestId('eval-calls')
  await expect(calls).toContainText('1 call')
  await expect(calls).toContainText('6.0s')
  await expect(calls).not.toContainText('avg')
})

test('an unpriced run says so rather than showing zero', async ({ page }) => {
  await stubApi(page, { agents: [{ ...TOOL_AGENT, agent_type: 'labeler' }] })
  await runEval(page, UNPRICED_RESULT)

  const calls = page.getByTestId('eval-calls')
  await expect(calls).toContainText('unpriced')
  await expect(calls).not.toContainText('$0.00')
})

test('a row the agent never answered shows its error', async ({ page }) => {
  await stubApi(page, { agents: [{ ...TOOL_AGENT, agent_type: 'labeler' }] })
  await runEval(page, FIELD_RESULT)

  // Counted apart from the wrong answers in the summary line.
  await expect(page.locator('.errored')).toContainText('1 never answered')

  // A failed call shows the error instead of an empty "Actual",
  // which would read as a confident empty answer.
  const failed = page.locator('.mismatch').nth(1)
  await expect(failed).toContainText('Connection refused')
  await expect(failed).not.toContainText('Actual')

  // The row that was merely wrong still shows what came back.
  await expect(page.locator('.mismatch').first()).toContainText('Actual')
})
