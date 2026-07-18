// Chatter engine-override guard — the regression test owed for the
// v0.26.3 fix, which shipped without one because no harness existed.
//
// The fix: an override that supplies no model is blocked client-side
// instead of being sent and failing server-side as a 400. Both
// branches are covered here — Ollama with an empty installed-model
// list (blocked), and `openai_compat` whose model comes from the
// environment (must still be allowed through).

import { test, expect } from '@playwright/test'
import { stubApi, AGENT } from './_helpers.js'

const OLLAMA_MODELS = [{ name: 'qwen2.5:14b' }, { name: 'llama3.2:3b' }]

// Match on the field's own <span class="label"> text, not the label's
// full text — the Provider select contains an "Agent default" option,
// so a substring match on "Agent" would resolve two fields.
const field = (page, name) =>
  page.locator(`label.field:has(span.label:text-is("${name}"))`)

const agentSelect = page => field(page, 'Agent').locator('select')
const providerSelect = page => field(page, 'Provider').locator('select')
const modelSelect = page => field(page, 'Model').locator('select')
const modelInput = page => page.locator('.model-input')
const warning = page => page.locator('.override-warn')
const chatPanel = page => page.locator('.chat-panel')
const placeholder = page => page.locator('.transcript-placeholder')

/** Open the Chatter page with the given stub data, agent preselected. */
async function openChatter(page, overrides) {
  await stubApi(page, overrides)
  await page.goto('/#/chatter')
  // The agent list loads on mount and preselects the first chatter.
  await expect(agentSelect(page)).toHaveValue(AGENT.name)
}

test('no override runs the agent default engine', async ({ page }) => {
  await openChatter(page, {
    providers: [{ name: 'ollama', ready: true }],
    models: OLLAMA_MODELS,
  })

  await expect(providerSelect(page)).toHaveValue('')
  await expect(chatPanel(page)).toBeVisible()
  await expect(warning(page)).toHaveCount(0)
})

test('ollama override with no installed models is blocked', async ({
  page,
}) => {
  await openChatter(page, {
    providers: [{ name: 'ollama', ready: true }],
    models: [],
  })

  await providerSelect(page).selectOption('ollama')

  // Blocked client-side: the panel is replaced by the placeholder and
  // the warning names the missing model, so no 400 is ever provoked.
  await expect(warning(page)).toContainText('No Ollama model to run')
  await expect(placeholder(page)).toBeVisible()
  await expect(chatPanel(page)).toHaveCount(0)
})

test('ollama override with installed models is allowed', async ({
  page,
}) => {
  await openChatter(page, {
    providers: [{ name: 'ollama', ready: true }],
    models: OLLAMA_MODELS,
  })

  await providerSelect(page).selectOption('ollama')

  // The agent's own model is installed, so it is seeded as the choice.
  await expect(modelSelect(page)).toHaveValue(AGENT.model)
  await expect(chatPanel(page)).toBeVisible()
  await expect(warning(page)).toHaveCount(0)
})

test('openai_compat with an environment model is allowed through', async ({
  page,
}) => {
  // The branch the v0.26.3 fix had to keep working: the provider
  // supplies its own model, so an empty input must NOT block the chat.
  await openChatter(page, {
    providers: [
      { name: 'openai_compat', ready: true, model: 'env-model' },
    ],
    models: [],
  })

  await providerSelect(page).selectOption('openai_compat')
  await expect(modelInput(page)).toHaveValue('env-model')
  await expect(chatPanel(page)).toBeVisible()

  // Clearing the field still leaves the environment model in play.
  await modelInput(page).fill('')
  await expect(warning(page)).toHaveCount(0)
  await expect(chatPanel(page)).toBeVisible()
})

test('openai_compat with no model anywhere is blocked', async ({
  page,
}) => {
  await openChatter(page, {
    providers: [{ name: 'openai_compat', ready: true }],
    models: [],
  })

  await providerSelect(page).selectOption('openai_compat')

  await expect(modelInput(page)).toHaveValue('')
  await expect(warning(page)).toContainText('Enter a model name')
  await expect(chatPanel(page)).toHaveCount(0)

  // Typing one unblocks it.
  await modelInput(page).fill('gpt-4o-mini')
  await expect(warning(page)).toHaveCount(0)
  await expect(chatPanel(page)).toBeVisible()
})

test('a not-ready provider is offered but unselectable, with the reason', async ({
  page,
}) => {
  await openChatter(page, {
    providers: [
      {
        name: 'anthropic',
        ready: false,
        detail: 'ANTHROPIC_API_KEY is not set',
      },
    ],
    models: [],
  })

  // A not-ready provider stays visible — so the user learns it exists
  // and why it is unavailable — but carries `disabled`, so it cannot
  // be chosen and can never provoke a failing start.
  const option = providerSelect(page).locator('option[value="anthropic"]')
  await expect(option).toHaveAttribute('disabled', '')
  await expect(option).toContainText('ANTHROPIC_API_KEY is not set')

  // Selecting it is refused, leaving the agent default in place.
  await expect(providerSelect(page)).toHaveValue('')
})

test('switching agent resets the override to the default', async ({
  page,
}) => {
  const second = { ...AGENT, name: 'other_chatter', model: 'llama3.2:3b' }
  await openChatter(page, {
    agents: [AGENT, second],
    providers: [{ name: 'ollama', ready: true }],
    models: OLLAMA_MODELS,
  })

  await providerSelect(page).selectOption('ollama')
  await expect(providerSelect(page)).toHaveValue('ollama')

  // An override must never silently carry across a different persona.
  await agentSelect(page).selectOption(second.name)
  await expect(providerSelect(page)).toHaveValue('')
})
