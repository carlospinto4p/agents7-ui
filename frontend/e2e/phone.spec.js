// The UI on a phone-sized screen.
//
// Below 640px the sidebar leaves the layout: a top bar carries the
// page name and a menu button, and the sidebar slides in as a drawer.
// No page may be wider than the screen; a wide table scrolls on its
// own. Asserts rendered geometry, not just that elements exist.

import { test, expect } from '@playwright/test'
import { stubApi } from './_helpers.js'

test.use({
  viewport: { width: 390, height: 844 },
  isMobile: true,
  hasTouch: true,
})

const PAGES = [
  'home',
  'catalog',
  'classes',
  'runner',
  'chatter',
  'engine',
  'eval',
  'reads',
]

const LABELER = {
  name: 'my_tagger',
  display_name: 'MyTagger',
  agent_type: 'labeler',
  provider: 'ollama',
  model: 'gemma4:12b',
  version: '1',
  description: 'Tags a user name with a category.',
}

// A run with a four-column per-category table, the widest the Eval
// page draws: on a 390px screen it does not fit.
const EVAL_RESULT = {
  agent: 'my_tagger',
  golden_set: 'golden_set.csv',
  fields: ['category'],
  total: 3,
  passed: 1,
  failed: 2,
  accuracy: 0.3333,
  per_field: { category: 0.3333 },
  per_category: {
    FEMALE_WITH_A_LONG_CATEGORY_NAME: {
      total: 3,
      passed: 1,
      accuracy: 0.3333,
    },
  },
  trajectory: null,
  mismatches: [],
}

const sidebar = page => page.locator('aside.sidebar')
const menuButton = page => page.getByRole('button', { name: 'Open menu' })

/** How far the page and the scroll area under the top bar overflow. */
async function overflow(page) {
  return page.evaluate(() => {
    const main = document.querySelector('main')
    return {
      page: document.documentElement.scrollWidth - window.innerWidth,
      main: main.scrollWidth - main.clientWidth,
    }
  })
}

test.beforeEach(async ({ page }) => {
  await stubApi(page, { agents: [LABELER] })
})

test('the sidebar is off screen and the top bar names the page', async ({
  page,
}) => {
  await page.goto('/#/catalog')

  await expect(page.locator('header.topbar')).toBeVisible()
  await expect(page.locator('.topbar-title')).toHaveText('Catalog')
  await expect(sidebar(page)).toBeHidden()

  // The page gets the whole width, not a width minus an icon rail.
  const main = await page.locator('main').boundingBox()
  expect(main.x).toBe(0)
  expect(main.width).toBe(390)
})

test('the menu opens the drawer and picking a page closes it', async ({
  page,
}) => {
  await page.goto('/#/home')
  await menuButton(page).click()

  await expect(sidebar(page)).toBeVisible()
  await expect(menuButton(page)).toHaveAttribute('aria-expanded', 'true')
  // Labels are shown in the drawer, unlike the old icon rail.
  await expect(
    sidebar(page).getByRole('link', { name: 'Runner' }),
  ).toContainText('Runner')

  await sidebar(page).getByRole('link', { name: 'Runner' }).click()

  await expect(page).toHaveURL(/#\/runner$/)
  await expect(sidebar(page)).toBeHidden()
  await expect(page.locator('.topbar-title')).toHaveText('Runner')
})

test('the backdrop and Escape close the drawer', async ({ page }) => {
  await page.goto('/#/home')

  await menuButton(page).click()
  await expect(sidebar(page)).toBeVisible()
  // The backdrop covers the page; tap it to the right of the drawer.
  await page.mouse.click(370, 400)
  await expect(sidebar(page)).toBeHidden()

  await menuButton(page).click()
  await expect(sidebar(page)).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(sidebar(page)).toBeHidden()
})

for (const name of PAGES) {
  test(`the ${name} page is no wider than the screen`, async ({ page }) => {
    await page.goto(`/#/${name}`)
    await expect(page.locator('main .content')).not.toBeEmpty()
    expect(await overflow(page)).toEqual({ page: 0, main: 0 })
  })
}

test('a wide table scrolls on its own, not the page', async ({ page }) => {
  await page.route('**/api/eval/**', route =>
    route.fulfill({ json: EVAL_RESULT }),
  )
  await page.goto('/#/eval')
  await page.getByRole('button', { name: 'Run Eval' }).click()

  const table = page.locator('table', { hasText: 'FEMALE_WITH' })
  await expect(table).toBeVisible()

  const box = await table.boundingBox()
  expect(box.x + box.width).toBeLessThanOrEqual(390)
  expect(
    await table.evaluate(t => t.scrollWidth > t.clientWidth),
  ).toBe(true)
  expect(await overflow(page)).toEqual({ page: 0, main: 0 })
})

test('the page can be installed to the home screen', async ({ page }) => {
  await page.goto('/')

  const href = await page
    .locator('link[rel="manifest"]')
    .getAttribute('href')
  const manifest = await (await page.request.get(href)).json()
  expect(manifest.display).toBe('standalone')

  const sizes = manifest.icons.map(icon => icon.sizes)
  expect(sizes).toEqual(expect.arrayContaining(['192x192', '512x512']))
  for (const icon of manifest.icons) {
    const r = await page.request.get(icon.src)
    expect(r.ok()).toBe(true)
  }
})
