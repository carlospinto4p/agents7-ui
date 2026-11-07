// The Catalog detail page's "Character" section — the tabbed panel
// that shows a roleplay agent's persona, scene, and context guard.
//
// Only the tabs an agent actually has are rendered, and an agent with
// none of the three gets no section at all.

import { test, expect } from '@playwright/test'
import { stubApi } from './_helpers.js'

const PERSONA = {
  full_name: 'David García López',
  birthdate: '1990-12-04',
  nationality: 'Spanish',
  occupation: 'journalist',
  language: 'Spanish',
  physical: { height: '178 cm', build: 'medium', eyes: 'brown' },
  personality: ['curious', 'empathetic', 'witty'],
  backstory: 'Born and raised in Madrid.\nLives in Malasaña.',
  interests: ['politics', 'photography'],
  speaking_style: 'Casual and direct.',
  extra: { 'Favorite food': 'tortilla de patatas' },
}

const SCENE = {
  setting: 'Un café ruidoso en Malasaña.',
  situation: 'David se ha sentado con una fuente anónima.',
  time_period: 'Madrid, 2026',
  rules: ['You protect your source.', 'Redirect off-topic questions.'],
  other_characters: ['La fuente anónima.'],
  goal: 'Publish the story without exposing the source.',
}

const GUARDED_SCENE = {
  name: 'guarded_scene_david',
  display_name: 'David García López',
  agent_type: 'guarded_scene_chatter',
  provider: 'ollama',
  model: 'gemma4:e4b',
  version: 1,
  description: 'A journalist role-played inside a guarded scene.',
  source: 'example',
  persona: PERSONA,
  scene: SCENE,
  guard: {
    provider: 'ollama',
    model: 'gemma4:e4b',
    engine_inherited: false,
    think: true,
    forbidden_terms: ['as an AI'],
    persona_summary: null,
    settings: { max_guard_retries: 2, guard_context_turns: 3 },
  },
}

const PERSONA_ONLY = {
  name: 'friendly_assistant',
  display_name: 'Friendly Assistant',
  agent_type: 'chatter',
  provider: 'ollama',
  model: 'qwen2.5:3b',
  version: 1,
  description: 'A plain persona chatter.',
  source: 'example',
  persona: { full_name: 'Ana', occupation: 'guide' },
  scene: null,
  guard: null,
}

const PLAIN = {
  name: 'my_tagger',
  display_name: 'MyTagger',
  agent_type: 'classifier',
  provider: 'ollama',
  model: 'gemma3:12b',
  version: 11,
  description: 'Tags internet nicknames.',
  source: 'catalog',
  persona: null,
  scene: null,
  guard: null,
}

test.beforeEach(async ({ page }) => {
  await stubApi(page, { agents: [GUARDED_SCENE, PERSONA_ONLY, PLAIN] })
  for (const agent of [GUARDED_SCENE, PERSONA_ONLY, PLAIN]) {
    await page.route(`**/api/catalog/${agent.name}`, route =>
      route.fulfill({ json: agent }),
    )
  }
})

async function open(page, displayName) {
  await page.goto('/#/catalog')
  await page.getByText(displayName, { exact: true }).first().click()
  await expect(
    page.getByRole('heading', { name: displayName }).first(),
  ).toBeVisible()
}

test('a guarded scene agent gets all three tabs, persona first', async ({
  page,
}) => {
  await open(page, 'David García López')

  const tabs = page.locator('.char-tabs .tab-btn')
  await expect(tabs).toHaveText(['Persona', 'Scene', 'Guard'])
  await expect(tabs.filter({ hasText: 'Persona' })).toHaveClass(/active/)
})

test('the persona tab shows identity, traits, and prose fields', async ({
  page,
}) => {
  await open(page, 'David García López')

  const panel = page.locator('.char-panel')
  await expect(panel).toContainText('Nationality')
  await expect(panel).toContainText('Spanish')
  await expect(panel).toContainText('Physical appearance')
  await expect(panel).toContainText('178 cm')
  await expect(panel.locator('.badge.trait')).toContainText([
    'curious',
    'empathetic',
    'witty',
    'politics',
    'photography',
  ])
  await expect(panel).toContainText('Born and raised in Madrid.')
  await expect(panel).toContainText('Favorite food')
})

test('the scene tab shows the setting, rules, and other characters', async ({
  page,
}) => {
  await open(page, 'David García López')
  await page.locator('.char-tabs .tab-btn', { hasText: 'Scene' }).click()

  const panel = page.locator('.char-panel')
  await expect(panel).toContainText('Madrid, 2026')
  await expect(panel).toContainText('Un café ruidoso en Malasaña.')
  await expect(panel).toContainText('Rules (2)')
  await expect(panel.locator('.char-list li')).toContainText([
    'You protect your source.',
    'Redirect off-topic questions.',
    'La fuente anónima.',
  ])
  // Persona content is gone once another tab is active.
  await expect(panel).not.toContainText('Physical appearance')
})

test('the guard tab shows its model, tuning, and forbidden terms', async ({
  page,
}) => {
  await open(page, 'David García López')
  await page.locator('.char-tabs .tab-btn', { hasText: 'Guard' }).click()

  const panel = page.locator('.char-panel')
  await expect(panel).toContainText('ollama / gemma4:e4b')
  await expect(panel).toContainText('Max guard retries')
  await expect(panel).toContainText('Guard context turns')
  await expect(panel.locator('.badge.forbidden')).toHaveText('as an AI')
  // No explicit persona_summary — the panel says where it comes from.
  await expect(panel).toContainText('derived from the persona and scene')
})

test('an inherited guard engine is labelled as inherited', async ({
  page,
}) => {
  const inherited = {
    ...GUARDED_SCENE,
    guard: { ...GUARDED_SCENE.guard, engine_inherited: true },
  }
  await page.route('**/api/catalog/guarded_scene_david', route =>
    route.fulfill({ json: inherited }),
  )

  await open(page, 'David García López')
  await page.locator('.char-tabs .tab-btn', { hasText: 'Guard' }).click()

  await expect(page.locator('.kv-note')).toHaveText(
    'inherited from the agent',
  )
})

test('a persona-only agent gets a single tab', async ({ page }) => {
  await open(page, 'Friendly Assistant')

  await expect(page.locator('.char-tabs .tab-btn')).toHaveText(['Persona'])
  await expect(page.locator('.char-panel')).toContainText('Ana')
})

test('an agent with no persona, scene, or guard has no Character section', async ({
  page,
}) => {
  await open(page, 'MyTagger')

  await expect(page.locator('.character-section')).toHaveCount(0)
  // The runner is still there — the section is additive.
  await expect(
    page.getByRole('heading', { name: 'Runner' }),
  ).toBeVisible()
})
