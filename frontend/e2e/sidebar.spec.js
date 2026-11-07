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

// ── Narrow viewport (v0.45.0) ─────────────────────────────────────
//
// Below 640px the sidebar becomes an icon rail, so the page keeps
// most of the width instead of being squeezed into a column of
// one-word lines.

const NARROW = { width: 430, height: 900 }
const RAIL_MAX = 60

test('a narrow viewport collapses the sidebar to an icon rail', async ({
  page,
}) => {
  await page.setViewportSize(NARROW)
  await page.goto('/')
  await expect(sidebar(page)).toBeVisible()

  expect(await widthOf(page)).toBeLessThanOrEqual(RAIL_MAX)
  await expect(sidebar(page).locator('.nav-label').first()).toBeHidden()
  await expect(sidebar(page).locator('.brand-text')).toBeHidden()
  await expect(handle(page)).toBeHidden()

  // The point of the rail: the content gets the rest of the width.
  const main = await page.locator('main').boundingBox()
  expect(main.width).toBeGreaterThanOrEqual(NARROW.width - RAIL_MAX)
})

test('the icon rail still navigates, by accessible name', async ({
  page,
}) => {
  await page.setViewportSize(NARROW)
  await page.goto('/')

  // The label text is hidden, so the link's name has to come from
  // somewhere else or the rail is unusable to a screen reader.
  const link = sidebar(page).getByRole('link', { name: 'Eval' })
  await link.click()
  await expect(page).toHaveURL(/#\/eval$/)
  await expect(link).toHaveAttribute('aria-current', 'page')
})

test('the rail does not touch the stored width', async ({ page }) => {
  await page.goto('/')
  await dragHandle(page, 80)
  expect(await storedWidth(page)).toBe(String(DEFAULT_WIDTH + 80))

  await page.setViewportSize(NARROW)
  expect(await widthOf(page)).toBeLessThanOrEqual(RAIL_MAX)
  expect(await storedWidth(page)).toBe(String(DEFAULT_WIDTH + 80))

  // Wide again: the width the user chose comes back.
  await page.setViewportSize({ width: 1280, height: 900 })
  expect(await widthOf(page)).toBe(DEFAULT_WIDTH + 80)
})
