// Tool agents on the Runner page.
//
// A tool agent has no `system_examples` and no output model, so the
// page must fall back to a free-text input for it and render the
// answer plus the tool-call trajectory instead of an output table.
// Asserts the rendered DOM, not just that a request was made.

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

// The shape `/api/run` returns for a tool agent: a flat event list
// covering two calls across two iterations, then the answer.
const RUN_RESULT = {
  agent: 'StoreAssistant',
  answer: 'Yes — we have 8 blue mugs in stock at EUR 12.50 each.',
  thinking: null,
  error: null,
  output: null,
  raw_response: 'Yes — we have 8 blue mugs in stock at EUR 12.50 each.',
  parse_error: false,
  tool_steps: [
    {
      kind: 'tool_call',
      iteration: 0,
      name: 'find_product',
      arguments: { query: 'blue mug' },
    },
    {
      kind: 'tool_result',
      iteration: 0,
      name: 'find_product',
      result: '{"sku": "MUG-01", "unit_price_cents": 1250}',
    },
    {
      kind: 'tool_call',
      iteration: 1,
      name: 'check_stock',
      arguments: { sku: 'MUG-01' },
    },
    {
      kind: 'tool_result',
      iteration: 1,
      name: 'check_stock',
      result: '{"units": 8}',
    },
    { kind: 'answer', iteration: 2 },
  ],
  metrics: {
    tokens: 412,
    prompt_tokens: 300,
    total_duration: 2.4,
    cost_cents: null,
  },
}

async function stubRun(page, json) {
  await page.route('**/api/run/**', route => route.fulfill({ json }))
}

async function openRunner(page) {
  await page.goto('/#/runner')
  await expect(page.getByRole('heading', { name: /runner/i })).toBeVisible()
}

test.beforeEach(async ({ page }) => {
  await stubApi(page, { agents: [TOOL_AGENT] })
})

test('a tool agent gets a free-text input despite having no examples', async ({
  page,
}) => {
  await openRunner(page)

  // Without the tool fallback this agent lands in 'none' mode and
  // shows "No input schema found" with Run permanently disabled.
  const input = page.locator('textarea')
  await expect(input).toBeVisible()
  await expect(page.getByText('No input schema found')).toHaveCount(0)

  const run = page.getByRole('button', { name: 'Run', exact: true })
  await expect(run).toBeDisabled()
  await input.fill('Any blue mugs?')
  await expect(run).toBeEnabled()
})

test('the answer and the tool trajectory are rendered', async ({ page }) => {
  await stubRun(page, RUN_RESULT)
  await openRunner(page)

  await page.locator('textarea').fill('Any blue mugs?')
  await page.getByRole('button', { name: 'Run', exact: true }).click()

  // The free-text answer, under an "Answer" label rather than the
  // structured-output "Output" one.
  await expect(page.getByText(RUN_RESULT.answer)).toBeVisible()
  await expect(page.getByText('Answer', { exact: true })).toBeVisible()

  // Both calls appear, paired with the result that answered them.
  const trajectory = page.getByTestId('tool-trajectory')
  await expect(trajectory).toBeVisible()
  await expect(trajectory.locator('.tool-step')).toHaveCount(2)
  await expect(trajectory).toContainText('find_product')
  await expect(trajectory).toContainText('check_stock')
  await expect(trajectory).toContainText('{"sku": "MUG-01"')
  await expect(trajectory).toContainText('{"units": 8}')

  // Arguments are rendered per call, not dumped as one blob.
  await expect(trajectory).toContainText('query')
  await expect(trajectory).toContainText('blue mug')
})

test('an exhausted loop shows the error and the calls it did make', async ({
  page,
}) => {
  await stubRun(page, {
    ...RUN_RESULT,
    answer: null,
    raw_response: null,
    parse_error: true,
    error: 'ToolAgent `StoreAssistant` exceeded 6 iterations.',
    tool_steps: RUN_RESULT.tool_steps.slice(0, 2),
    metrics: { ...RUN_RESULT.metrics, tokens: 0 },
  })
  await openRunner(page)

  await page.locator('textarea').fill('Any blue mugs?')
  await page.getByRole('button', { name: 'Run', exact: true }).click()

  await expect(page.getByText('loop error')).toBeVisible()
  await expect(page.getByText('exceeded 6 iterations')).toBeVisible()

  // The trajectory survives the error — it is what explains it.
  const trajectory = page.getByTestId('tool-trajectory')
  await expect(trajectory.locator('.tool-step')).toHaveCount(1)
  await expect(trajectory).toContainText('find_product')
})
