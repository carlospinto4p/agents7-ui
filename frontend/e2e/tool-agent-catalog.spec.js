// Tool agents in the Catalog page's embedded Runner.
//
// A tool agent has no `system_examples` and no output model. The
// Catalog detail view's inline runner must fall back to free text —
// same as the standalone Runner page — instead of the generic JSON
// placeholder, and must render the answer plus the tool-call
// trajectory instead of an output table.

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
  source: 'catalog',
}

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
    { kind: 'answer', iteration: 1 },
  ],
  metrics: {
    tokens: 412,
    prompt_tokens: 300,
    total_duration: 2.4,
    cost_cents: null,
  },
}

async function openCatalogDetail(page) {
  await page.goto('/#/catalog')
  await page.getByText('StoreAssistant', { exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'StoreAssistant' }),
  ).toBeVisible()
}

test.beforeEach(async ({ page }) => {
  await stubApi(page, { agents: [TOOL_AGENT] })
  await page.route('**/api/catalog/store_assistant', route =>
    route.fulfill({ json: TOOL_AGENT }),
  )
})

test('a tool agent gets a free-text input despite having no examples', async ({
  page,
}) => {
  await openCatalogDetail(page)

  const input = page.locator('textarea, input[type="text"]').first()
  await expect(input).toBeVisible()
  await expect(page.getByText('JSON Input')).toHaveCount(0)

  const run = page.getByRole('button', { name: 'Run', exact: true })
  await expect(run).toBeDisabled()
  await input.fill('Any blue mugs?')
  await expect(run).toBeEnabled()
})

test('the answer and the tool trajectory are rendered', async ({ page }) => {
  await page.route('**/api/run/store_assistant', route =>
    route.fulfill({ json: RUN_RESULT }),
  )
  await openCatalogDetail(page)

  await page.locator('textarea, input[type="text"]').first().fill('Any blue mugs?')
  await page.getByRole('button', { name: 'Run', exact: true }).click()

  await expect(page.getByText(RUN_RESULT.answer)).toBeVisible()
  await expect(page.getByText('Answer', { exact: true })).toBeVisible()

  const trajectory = page.getByTestId('tool-trajectory')
  await expect(trajectory).toBeVisible()
  await expect(trajectory).toContainText('find_product')
  await expect(trajectory).toContainText('{"sku": "MUG-01"')
  await expect(page.getByTestId('tool-rejected')).toHaveCount(0)
})

test('a call the tool rejected is marked, not shown as a result', async ({
  page,
}) => {
  await page.route('**/api/run/store_assistant', route =>
    route.fulfill({
      json: {
        ...RUN_RESULT,
        answer: 'Sorry, I could not find that product.',
        raw_response: 'Sorry, I could not find that product.',
        tool_steps: [
          {
            kind: 'tool_call',
            iteration: 0,
            name: 'find_product',
            arguments: { query: { type: 'string', value: 'blue mug' } },
          },
          {
            kind: 'tool_result',
            iteration: 0,
            name: 'find_product',
            result: 'Error: Invalid arguments for `find_product`',
            error: 'Invalid arguments for `find_product`',
          },
          { kind: 'answer', iteration: 1 },
        ],
      },
    }),
  )
  await openCatalogDetail(page)

  await page
    .locator('textarea, input[type="text"]')
    .first()
    .fill('Any blue mugs?')
  await page.getByRole('button', { name: 'Run', exact: true }).click()

  const trajectory = page.getByTestId('tool-trajectory')
  await expect(page.getByTestId('tool-rejected')).toBeVisible()
  await expect(trajectory.locator('.tool-step')).toHaveClass(/rejected/)
  await expect(trajectory.locator('.tool-result.rejected')).toHaveCount(1)
  await expect(trajectory.getByText('Result', { exact: true })).toHaveCount(0)
})
