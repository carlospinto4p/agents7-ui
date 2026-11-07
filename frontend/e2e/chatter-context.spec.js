// Per-conversation context on the Chatter page.
//
// An agent can declare values it expects the caller to supply — the
// nickname of the person it is talking to, for instance. The page
// renders one field per declaration and sends the values when the
// chat session starts, since they are baked into the system prompt
// and cannot change mid-conversation.
//
// A value the framework computes itself (a `callable`, e.g. the
// clock) is reported with `supplied_by_caller` false and must NOT
// get a field — there is nothing for a human to type.

import { test, expect } from '@playwright/test'
import { stubApi, AGENT } from './_helpers.js'

const DETAIL_WITH_CONTEXT = {
  persona: null,
  scene: null,
  context_params: [
    {
      name: 'nick',
      default: 'alguien',
      description: "The other person's nickname",
      supplied_by_caller: true,
    },
    {
      name: 'moment',
      default: '',
      description: 'Time of day',
      supplied_by_caller: false,
    },
  ],
}

const field = (page, name) =>
  page.locator(`label.field:has(span.label:text-is("${name}"))`)

const agentSelect = page => field(page, 'Agent').locator('select')
const contextInput = (page, name) =>
  page.locator(`.context-input[data-context-param="${name}"]`)

/**
 * Open the Chatter page and record every chat-start request body.
 *
 * @returns An array that accumulates the parsed bodies, in order.
 */
async function openChatter(page, overrides = {}) {
  await stubApi(page, { detail: DETAIL_WITH_CONTEXT, ...overrides })

  const startBodies = []
  // Registered after stubApi, so it wins over the catch-all.
  await page.route('**/api/chat/start/**', route => {
    startBodies.push(route.request().postDataJSON() ?? {})
    route.fulfill({ json: { session_id: 'sess-1' } })
  })

  await page.goto('/#/chatter')
  await expect(agentSelect(page)).toHaveValue(AGENT.name)
  return startBodies
}

test('a declared context value gets its own field', async ({ page }) => {
  await openChatter(page)

  const input = contextInput(page, 'nick')
  await expect(input).toBeVisible()
  // The declared default is the placeholder, so the user can see what
  // the agent falls back to without it being pre-filled as a value.
  await expect(input).toHaveAttribute('placeholder', 'alguien')
  await expect(input).toHaveValue('')
})

test('a framework-computed value gets no field', async ({ page }) => {
  await openChatter(page)

  // `moment` is resolved by a callable on every message; there is
  // nothing for a human to supply, so no input is rendered.
  await expect(contextInput(page, 'moment')).toHaveCount(0)
  await expect(contextInput(page, 'nick')).toHaveCount(1)
})

test('the hint names each field and what it means', async ({ page }) => {
  await openChatter(page)

  const hint = page.locator('.context-hint')
  await expect(hint).toContainText('nick')
  await expect(hint).toContainText("The other person's nickname")
  await expect(hint).not.toContainText('Time of day')
})

test('a value derived from a field gets a line, not a field', async ({
  page,
}) => {
  const detail = {
    ...DETAIL_WITH_CONTEXT,
    context_params: [
      ...DETAIL_WITH_CONTEXT.context_params,
      {
        name: 'nick_hint',
        default: '',
        description: 'What the nick suggests',
        supplied_by_caller: false,
        derived_from: 'nick',
      },
    ],
  }
  await openChatter(page, { detail })

  // Typing `nick` is all there is to do: the framework computes the
  // hint from it, so the page says so instead of asking for it.
  await expect(contextInput(page, 'nick_hint')).toHaveCount(0)
  await expect(
    page.locator('.context-derived[data-derived-param="nick_hint"]'),
  ).toHaveText(/nick_hint\s+is worked out from\s+nick\./)
  // `moment` is computed too, but from the clock, not from a field.
  await expect(page.locator('.context-derived')).toHaveCount(1)
})

test('an agent declaring nothing shows no context controls', async ({
  page,
}) => {
  await openChatter(page, { detail: { persona: null, scene: null } })

  await expect(page.locator('.context-input')).toHaveCount(0)
  await expect(page.locator('.context-hint')).toHaveCount(0)
})

test('the typed value is sent when the session starts', async ({
  page,
}) => {
  const startBodies = await openChatter(page)
  expect(startBodies.length).toBe(1)
  // Nothing typed yet, so the first start carries no context and the
  // agent falls back to its declared default.
  expect(startBodies[0].context).toBeUndefined()

  // Committing on change (not per keystroke) restarts the session
  // once, with the value.
  await contextInput(page, 'nick').fill('Monica28')
  await contextInput(page, 'nick').blur()

  await expect.poll(() => startBodies.length).toBe(2)
  expect(startBodies[1].context).toEqual({ nick: 'Monica28' })
})

test('typing does not restart the session on every keystroke', async ({
  page,
}) => {
  const startBodies = await openChatter(page)

  await contextInput(page, 'nick').pressSequentially('Ana', { delay: 20 })
  // Still uncommitted — the field has not been left yet.
  await expect(contextInput(page, 'nick')).toHaveValue('Ana')
  expect(startBodies.length).toBe(1)
})

test('a blank value is not sent, so the default applies', async ({
  page,
}) => {
  const startBodies = await openChatter(page)

  await contextInput(page, 'nick').fill('   ')
  await contextInput(page, 'nick').blur()

  // Whitespace carries no value, so there is nothing new to send and
  // the running conversation is left alone rather than restarted.
  await expect(contextInput(page, 'nick')).toHaveValue('   ')
  expect(startBodies.length).toBe(1)
  expect(startBodies[0].context).toBeUndefined()
})

test('clearing a committed value restarts on the default', async ({
  page,
}) => {
  const startBodies = await openChatter(page)

  await contextInput(page, 'nick').fill('Monica28')
  await contextInput(page, 'nick').blur()
  await expect.poll(() => startBodies.length).toBe(2)

  // Emptying the field is a real change: the session restarts and the
  // agent goes back to its declared default.
  await contextInput(page, 'nick').fill('')
  await contextInput(page, 'nick').blur()
  await expect.poll(() => startBodies.length).toBe(3)
  expect(startBodies[2].context).toBeUndefined()
})

test('switching agent clears the context', async ({ page }) => {
  const second = { ...AGENT, name: 'other_chatter' }
  const startBodies = await openChatter(page, {
    agents: [AGENT, second],
  })

  await contextInput(page, 'nick').fill('Monica28')
  await contextInput(page, 'nick').blur()
  await expect.poll(() => startBodies.length).toBe(2)

  // A nickname belongs to the agent it was typed for; it must not
  // carry across to a different persona.
  await agentSelect(page).selectOption(second.name)
  await expect(contextInput(page, 'nick')).toHaveValue('')
  await expect
    .poll(() => startBodies[startBodies.length - 1].context)
    .toBeUndefined()
})
