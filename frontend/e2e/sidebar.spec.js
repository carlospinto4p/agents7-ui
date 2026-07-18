// Sidebar drag-to-resize and width persistence (v0.22.0).
//
// Asserts the rendered layout, not just text: the sidebar's actual
// pixel width is read from its bounding box, so a CSS or clamping
// regression fails here.

import { test, expect } from '@playwright/test'
import { stubApi } from './_helpers.js'

const KEY = 'agents7.sidebarWidth'
const DEFAULT_WIDTH = 300
const MIN_WIDTH = 180
const MAX_WIDTH = 420

test.beforeEach(async ({ page }) => {
  await stubApi(page)
})

const sidebar = page => page.locator('aside.sidebar')
const handle = page =>
  page.getByRole('button', { name: 'Resize sidebar' })

async function widthOf(page) {
  const box = await sidebar(page).boundingBox()
  return box.width
}

async function dragHandle(page, dx) {
  const box = await handle(page).boundingBox()
  const x = box.x + box.width / 2
  const y = box.y + box.height / 2
  await page.mouse.move(x, y)
  await page.mouse.down()
  await page.mouse.move(x + dx, y, { steps: 10 })
  await page.mouse.up()
}

async function storedWidth(page) {
  return page.evaluate(k => localStorage.getItem(k), KEY)
}

test('defaults to 300px when nothing is stored', async ({ page }) => {
  await page.goto('/')
  await expect(sidebar(page)).toBeVisible()
  expect(await widthOf(page)).toBe(DEFAULT_WIDTH)
})

test('drag widens the sidebar and persists across a reload', async ({
  page,
}) => {
  await page.goto('/')
  await expect(sidebar(page)).toBeVisible()

  await dragHandle(page, 80)
  expect(await widthOf(page)).toBe(DEFAULT_WIDTH + 80)
  expect(await storedWidth(page)).toBe(String(DEFAULT_WIDTH + 80))

  // The width survives a full reload — this is the persistence half
  // of the feature, and the reason the value is written on mouseup.
  await page.reload()
  await expect(sidebar(page)).toBeVisible()
  expect(await widthOf(page)).toBe(DEFAULT_WIDTH + 80)
})

test('drag clamps to the minimum width', async ({ page }) => {
  await page.goto('/')
  await expect(sidebar(page)).toBeVisible()

  await dragHandle(page, -400)
  expect(await widthOf(page)).toBe(MIN_WIDTH)
})

test('drag clamps to the maximum width', async ({ page }) => {
  await page.goto('/')
  await expect(sidebar(page)).toBeVisible()

  await dragHandle(page, 600)
  expect(await widthOf(page)).toBe(MAX_WIDTH)
})

test('double-click on the handle resets to the default width', async ({
  page,
}) => {
  await page.goto('/')
  await expect(sidebar(page)).toBeVisible()

  await dragHandle(page, 100)
  expect(await widthOf(page)).toBe(DEFAULT_WIDTH + 100)

  await handle(page).dblclick()
  expect(await widthOf(page)).toBe(DEFAULT_WIDTH)
  expect(await storedWidth(page)).toBe(String(DEFAULT_WIDTH))
})

test('arrow keys nudge the width and Home/End jump to the bounds', async ({
  page,
}) => {
  await page.goto('/')
  await expect(sidebar(page)).toBeVisible()

  await handle(page).focus()

  await page.keyboard.press('ArrowRight')
  expect(await widthOf(page)).toBe(DEFAULT_WIDTH + 8)

  await page.keyboard.press('Shift+ArrowRight')
  expect(await widthOf(page)).toBe(DEFAULT_WIDTH + 8 + 24)

  await page.keyboard.press('ArrowLeft')
  expect(await widthOf(page)).toBe(DEFAULT_WIDTH + 8 + 24 - 8)

  await page.keyboard.press('Home')
  expect(await widthOf(page)).toBe(MIN_WIDTH)

  await page.keyboard.press('End')
  expect(await widthOf(page)).toBe(MAX_WIDTH)

  // Keyboard resizing persists too, without needing a mouseup.
  expect(await storedWidth(page)).toBe(String(MAX_WIDTH))
})

test('an out-of-range stored width falls back to the default', async ({
  page,
}) => {
  // Guards `loadWidth()` — a stale or hand-edited value outside the
  // clamp must not be honoured.
  await page.addInitScript(
    ([k, v]) => localStorage.setItem(k, v),
    [KEY, '9999'],
  )
  await page.goto('/')
  await expect(sidebar(page)).toBeVisible()

  expect(await widthOf(page)).toBe(DEFAULT_WIDTH)
})
