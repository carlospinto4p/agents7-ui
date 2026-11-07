// The Catalog page's "Demonstrates" field — a sample's framework
// class (and optional feature), shown as badges separate from its
// description rather than as a prose sentence.

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
  demonstrates: { class: 'Labeler', feature: 'prose writing' },
  source: 'example',
}

const CLASS_ONLY_AGENT = {
  name: 'sentiment_classifier',
  display_name: 'SentimentClassifier',
  agent_type: 'classifier',
  provider: 'ollama',
  model: 'gemma3:12b',
  version: 1,
  description: 'Classifies sentiment.',
  demonstrates: { class: 'Classifier' },
  source: 'integration_test',
}

const CATALOG_AGENT = {
  name: 'my_tagger',
  display_name: 'MyTagger',
  agent_type: 'classifier',
  provider: 'ollama',
  model: 'gemma3:12b',
  version: 11,
  description: 'Tags internet nicknames.',
  source: 'catalog',
}

test.beforeEach(async ({ page }) => {
  await stubApi(page, {
    agents: [SAMPLE_AGENT, CLASS_ONLY_AGENT, CATALOG_AGENT],
  })
  await page.route('**/api/catalog/bio_generator', route =>
    route.fulfill({ json: SAMPLE_AGENT }),
  )
})

test('a sample card shows Demonstrates as class and feature badges', async ({
  page,
}) => {
  await page.goto('/#/catalog')

  const card = page.locator('.card', { hasText: 'BioGenerator' })
  await expect(card).toContainText('Writes a short biography')
  await expect(card).toContainText('Demonstrates')
  await expect(card.locator('.badge.demo-class')).toHaveText('Labeler')
  await expect(card.locator('.badge.demo-feature')).toHaveText(
    'prose writing',
  )
})

test('a class-only sample shows no feature badge', async ({ page }) => {
  await page.goto('/#/catalog')

  const card = page.locator('.card', { hasText: 'SentimentClassifier' })
  await expect(card.locator('.badge.demo-class')).toHaveText('Classifier')
  await expect(card.locator('.badge.demo-feature')).toHaveCount(0)
})

test('a catalog agent with no demonstrates field shows no such label', async ({
  page,
}) => {
  await page.goto('/#/catalog')

  const card = page.locator('.card', { hasText: 'MyTagger' })
  await expect(card).not.toContainText('Demonstrates')
})

test('the detail page shows Demonstrates as badges, not in the description', async ({
  page,
}) => {
  await page.goto('/#/catalog')
  await page.getByText('BioGenerator', { exact: true }).click()

  const description = page.locator('.detail-desc')
  await expect(description).toContainText('Writes a short biography')
  await expect(description).not.toContainText('Demonstrates')

  const demoRow = page.locator('.demonstrates-row')
  await expect(demoRow).toBeVisible()
  await expect(demoRow).toContainText('Demonstrates')
  await expect(demoRow.locator('.badge.demo-class')).toHaveText('Labeler')
  await expect(demoRow.locator('.badge.demo-feature')).toHaveText(
    'prose writing',
  )
})
