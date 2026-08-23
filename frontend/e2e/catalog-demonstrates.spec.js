// The Catalog page's "Demonstrates" field — a sample's framework
// capability, shown separately from its description rather than
// appended to it.

import { test, expect } from '@playwright/test'
import { stubApi } from './_helpers.js'

const SAMPLE_AGENT = {
  name: 'bio_generator',
  display_name: 'BioGenerator',
  agent_type: 'labeler',
  provider: 'ollama',
  model: 'qwen2.5:3b',
  version: 1,
  description: 'Writes a short biography from structured details.',
  demonstrates: 'A `Labeler` writing free-form prose.',
  source: 'example',
}

const CATALOG_AGENT = {
  name: 'tagger_agent',
  display_name: 'Tagger agent',
  agent_type: 'classifier',
  provider: 'ollama',
  model: 'gemma3:12b',
  version: 11,
  description: 'Tags internet nicknames.',
  source: 'catalog',
}

test.beforeEach(async ({ page }) => {
  await stubApi(page, { agents: [SAMPLE_AGENT, CATALOG_AGENT] })
  await page.route('**/api/catalog/bio_generator', route =>
    route.fulfill({ json: SAMPLE_AGENT }),
  )
})

test('a sample card shows Demonstrates separately from its description', async ({
  page,
}) => {
  await page.goto('/#/catalog')

  const card = page.locator('.card', { hasText: 'BioGenerator' })
  await expect(card).toContainText('Writes a short biography')
  await expect(card).toContainText('Demonstrates')
  await expect(card).toContainText('A `Labeler` writing free-form prose.')
})

test('a catalog agent with no demonstrates field shows no such label', async ({
  page,
}) => {
  await page.goto('/#/catalog')

  const card = page.locator('.card', { hasText: 'Tagger agent' })
  await expect(card).not.toContainText('Demonstrates')
})

test('the detail page shows Demonstrates in its own box, not the description', async ({
  page,
}) => {
  await page.goto('/#/catalog')
  await page.getByText('BioGenerator', { exact: true }).click()

  const description = page.locator('.detail-desc')
  await expect(description).toContainText('Writes a short biography')
  await expect(description).not.toContainText('Demonstrates')

  const demoBox = page.locator('.demonstrates-box')
  await expect(demoBox).toBeVisible()
  await expect(demoBox).toContainText('Demonstrates')
  await expect(demoBox).toContainText('A `Labeler` writing free-form prose.')
})
