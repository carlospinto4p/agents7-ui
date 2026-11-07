// Feeding back on a read without the mouse.
//
// Judging a read is dozens of corrections in a row. With a click to
// open each form and another to save it, the mouse round trip is
// most of the cost, so the whole loop has a keyboard path: open,
// type, save, land on the next turn.

import { test, expect } from '@playwright/test'
import { openRead } from './_reads.js'

const addButton = (page, turn) =>
  page.getByRole('button', { name: `+ Feedback on turn ${turn}` })
const form = page => page.getByRole('form', { name: 'Feedback' })
const shouldSay = page => form(page).locator('textarea').first()

test('opening the form puts the caret in the first field', async ({
  page,
}) => {
  await openRead(page)

  await addButton(page, 1).focus()
  await page.keyboard.press('Enter')

  await expect(shouldSay(page)).toBeFocused()
})

test('ctrl+enter saves from any field and moves to the next turn', async ({
  page,
}) => {
  const saves = await openRead(page)

  await addButton(page, 1).focus()
  await page.keyboard.press('Enter')
  await page.keyboard.type('pues un gato, Pixel')
  // Two tabs on: past "Why", into "Rule" — not the first field.
  await page.keyboard.press('Tab')
  await page.keyboard.press('Tab')
  await page.keyboard.type('nombra al perro')
  await page.keyboard.press('Control+Enter')

  await expect(form(page)).toHaveCount(0)
  expect(saves).toHaveLength(1)
  expect(saves[0].entries[0]).toMatchObject({
    conversation: 'warm',
    turn: 1,
    should_say: 'pues un gato, Pixel',
    rule: 'nombra al perro',
  })
  await expect(addButton(page, 2)).toBeFocused()
})

test('ctrl+enter on an empty form saves nothing', async ({ page }) => {
  const saves = await openRead(page)

  await addButton(page, 1).focus()
  await page.keyboard.press('Enter')
  await page.keyboard.press('Control+Enter')

  await expect(form(page)).toBeVisible()
  expect(saves).toHaveLength(0)
})

test('escape cancels and returns to the same turn', async ({ page }) => {
  const saves = await openRead(page)

  await addButton(page, 2).focus()
  await page.keyboard.press('Enter')
  await page.keyboard.type('algo')
  await page.keyboard.press('Escape')

  await expect(form(page)).toHaveCount(0)
  expect(saves).toHaveLength(0)
  await expect(addButton(page, 2)).toBeFocused()
})

test('arrow keys step between turns', async ({ page }) => {
  await openRead(page)

  await addButton(page, 1).focus()
  await page.keyboard.press('ArrowDown')
  await expect(addButton(page, 2)).toBeFocused()

  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('ArrowDown')
  // Three turns, so the last one holds.
  await expect(addButton(page, 3)).toBeFocused()

  await page.keyboard.press('ArrowUp')
  await expect(addButton(page, 2)).toBeFocused()
})
