import { test, expect } from '@playwright/test'
import { mockBackendApis, mockBackendDown, MOCK_MANAGERS } from './fixtures/api-mocks'
import { DashboardPage } from './pages/DashboardPage'

test.describe('Dashboard', () => {
  test.describe('with backend connected', () => {
    test.beforeEach(async ({ page }) => {
      await mockBackendApis(page)
    })

    test('shows status cards', async ({ page }) => {
      const dashboard = new DashboardPage(page)
      await dashboard.goto()

      await expect(page.getByText('BACKEND', { exact: true }).or(page.getByText('Backend', { exact: true }))).toBeVisible()
      await expect(page.getByText('Connected')).toBeVisible()
      // Use exact match to avoid strict-mode violation with heading containing city
      await expect(page.getByText('Austin, TX', { exact: true }).first()).toBeVisible()
      await expect(page.getByText('API KEY', { exact: true }).or(page.getByText('API key', { exact: true }))).toBeVisible()
    })

    test('shows configured city in heading', async ({ page }) => {
      const dashboard = new DashboardPage(page)
      await dashboard.goto()

      await expect(page.getByRole('heading', { name: /Finding rentals in Austin, TX/i })).toBeVisible()
    })

    test('shows Run discovery button when preferences configured', async ({ page }) => {
      const dashboard = new DashboardPage(page)
      await dashboard.goto()

      await expect(dashboard.runDiscoveryBtn).toBeVisible()
      await expect(dashboard.runDiscoveryBtn).toBeEnabled()
    })

    test('shows discovery log panel', async ({ page }) => {
      const dashboard = new DashboardPage(page)
      await dashboard.goto()

      await expect(page.getByText('Discovery log', { exact: false })).toBeVisible()
      await expect(page.getByText('Output will appear here when you run a discovery.')).toBeVisible()
    })

    test('shows run history when runs exist', async ({ page }) => {
      const dashboard = new DashboardPage(page)
      await dashboard.goto()

      await expect(page.getByText('Run history', { exact: false })).toBeVisible()
      // run status badge
      await expect(page.getByText('success').first()).toBeVisible()
    })

    test('shows property managers section', async ({ page }) => {
      const dashboard = new DashboardPage(page)
      await dashboard.goto()

      await expect(page.getByText('Property managers', { exact: true })).toBeVisible()
      await expect(page.getByText(MOCK_MANAGERS[0].name)).toBeVisible()
      await expect(page.getByText(MOCK_MANAGERS[1].name)).toBeVisible()
    })

    test('shows validated badge on validated managers', async ({ page }) => {
      const dashboard = new DashboardPage(page)
      await dashboard.goto()

      await expect(page.getByText('validated')).toBeVisible()
    })

    test('expanding a run history row shows logs', async ({ page }) => {
      const dashboard = new DashboardPage(page)
      await dashboard.goto()

      // wait for run history to load
      await expect(page.getByText('success').first()).toBeVisible()

      // click first run row button (contains status badge)
      const runRow = page.getByRole('button').filter({ hasText: 'success' }).first()
      await runRow.click()

      await expect(page.getByText('Starting discovery for Austin, TX')).toBeVisible()
      await expect(page.getByText('Found 2 property managers')).toBeVisible()
    })

    test('shows preference description', async ({ page }) => {
      const dashboard = new DashboardPage(page)
      await dashboard.goto()

      await expect(page.getByText('Looking for a 2BR near downtown')).toBeVisible()
    })
  })

  test.describe('with backend offline', () => {
    test('shows offline status', async ({ page }) => {
      await mockBackendDown(page)
      await page.goto('/')

      await expect(page.getByText('Offline')).toBeVisible()
    })

    test('Run discovery button is disabled when backend offline', async ({ page }) => {
      await mockBackendDown(page)
      await page.goto('/')

      const btn = page.getByRole('button', { name: /Run discovery/i })
      await expect(btn).toBeDisabled()
    })
  })

  test.describe('no preferences configured', () => {
    test('prompts user to configure preferences', async ({ page }) => {
      await page.route('**/health', (route) => route.fulfill({ json: { status: 'ok' } }))
      await page.route('**/api/preferences', (route) => route.fulfill({ json: [] }))
      await page.route('**/api/discovery/runs', (route) => route.fulfill({ json: [] }))
      await page.route('**/api/discovery/cities/*/managers', (route) => route.fulfill({ json: [] }))
      await page.route('**/api/listings', (route) => route.fulfill({ json: { listings: [], total: 0 } }))

      await page.goto('/')

      await expect(page.getByRole('link', { name: 'Configure your preferences' })).toBeVisible()
    })
  })
})
