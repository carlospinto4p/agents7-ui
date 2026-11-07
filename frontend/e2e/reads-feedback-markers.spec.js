// Seeing what has been judged without scrolling to it.
//
// The entries on a turn sit under that turn, so on a long
// conversation they are spread over several screens. Two markers
// answer "what is done and what is left" at a glance: a count on each
// conversation's tab, and a strip of turn numbers above the thread.

import { test, expect } from '@playwright/test'
import { openRead } from './_reads.js'

function entry(conversation, turn, why) {
  return {
    conversation,
    turn,
    verdict: 'wrong',
    he_said: '',
    should_say: '',
    why,
    rule: '',
    lands_in: '',
    shipped: '',
  }
}

// Two on turn 1, one on turn 3, one on the whole conversation.
const ENTRIES = [
  entry('warm', 1, 'suena a ficha'),
  entry('warm', 1, 'dos frases donde cabe una'),
  entry('warm', 3, 'pregunta demasiado pronto'),
  entry('warm', null, 'no lleva él la conversación'),
]

const tab = (page, name) =>
  page.locator('.tabs button').filter({ hasText: name })
const mark = (page, turn) =>
  page.locator('.turnmap .mark').filter({ hasText: String(turn) })
const label = page => page.locator('.turnmap .maplabel')

test('each conversation tab counts its entries', async ({ page }) => {
  await openRead(page, ENTRIES)

  await expect(tab(page, 'Warm').locator('.count')).toHaveText('4')
  // No entries, so no zero to read past.
  await expect(tab(page, 'Cold').locator('.count')).toHaveCount(0)
})

test('the strip marks the turns that carry feedback', async ({ page }) => {
  await openRead(page, ENTRIES)

  await expect(label(page)).toHaveText('Feedback on 2 of 3 turns')
  await expect(mark(page, 1)).toHaveClass(/has/)
  await expect(mark(page, 2)).not.toHaveClass(/has/)
  await expect(mark(page, 3)).toHaveClass(/has/)

  // The marking is a visible fill, not only a class.
  const fill = m =>
    m.evaluate(el => getComputedStyle(el).backgroundColor)
  expect(await fill(mark(page, 1))).not.toBe(await fill(mark(page, 2)))
})

test('saving feedback updates both markers', async ({ page }) => {
  await openRead(page, ENTRIES)

  await page
    .getByRole('button', { name: '+ Feedback on turn 2' })
    .click()
  await page.keyboard.type('mejor más corto')
  await page.keyboard.press('Control+Enter')

  await expect(mark(page, 2)).toHaveClass(/has/)
  await expect(label(page)).toHaveText('Feedback on 3 of 3 turns')
  await expect(tab(page, 'Warm').locator('.count')).toHaveText('5')
})

test('a mark jumps to its turn', async ({ page }) => {
  await openRead(page, ENTRIES)

  await mark(page, 3).click()

  await expect(
    page.getByRole('button', { name: '+ Feedback on turn 3' }),
  ).toBeFocused()
})

test('Read mode shows neither marker', async ({ page }) => {
  await openRead(page, ENTRIES)

  await page.getByRole('button', { name: 'Read', exact: true }).click()

  await expect(page.locator('.turnmap')).toHaveCount(0)
  await expect(page.locator('.tabs .count')).toHaveCount(0)
})
