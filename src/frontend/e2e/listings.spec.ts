import { test, expect } from '@playwright/test'
import { mockBackendApis, MOCK_LISTINGS, MOCK_SEARCH_RUN } from './fixtures/api-mocks'
import { ListingsPage } from './pages/ListingsPage'

test.describe('Listings page', () => {
  test.describe('all listings view (no run filter)', () => {
    test.beforeEach(async ({ page }) => {
      await mockBackendApis(page)
    })

    test('shows listings heading', async ({ page }) => {
      const listings = new ListingsPage(page)
      await listings.goto()

      await expect(page.getByRole('heading', { name: /Listings/i })).toBeVisible()
    })

    test('renders listing cards with address, price, beds, baths', async ({ page }) => {
      const listings = new ListingsPage(page)
      await listings.goto()

      await expect(page.getByText(MOCK_LISTINGS[0].address)).toBeVisible()
      await expect(page.getByText('$2,200/mo')).toBeVisible()
      await expect(page.getByText('2BR')).toBeVisible()
      await expect(page.getByText('1BA').first()).toBeVisible()
    })

    test('shows score badges', async ({ page }) => {
      const listings = new ListingsPage(page)
      await listings.goto()

      await expect(page.getByText('78/100')).toBeVisible()
      await expect(page.getByText('45/100')).toBeVisible()
    })

    test('shows score explanation', async ({ page }) => {
      const listings = new ListingsPage(page)
      await listings.goto()

      await expect(page.getByText(/Close to downtown/i)).toBeVisible()
    })

    test('shows "View source" link for listings with url', async ({ page }) => {
      const listings = new ListingsPage(page)
      await listings.goto()

      const viewLinks = page.getByRole('link', { name: 'View source' })
      await expect(viewLinks.first()).toBeVisible()
    })

    test('empty state shown when no listings', async ({ page }) => {
      await page.route('**/api/listings', (route) =>
        route.fulfill({ json: { listings: [], total: 0 } }),
      )
      await page.route('**/health', (route) => route.fulfill({ json: { status: 'ok' } }))
      await page.route('**/api/preferences', (route) =>
        route.fulfill({
          json: [
            {
              id: 1,
              city: 'Austin, TX',
              has_openrouter_api_key: true,
              openrouter_key_last4: 'ab12',
            },
          ],
        }),
      )

      const listings = new ListingsPage(page)
      await listings.goto()

      await expect(page.getByText('No listings yet')).toBeVisible()
      await expect(page.getByRole('link', { name: 'Dashboard' }).first()).toBeVisible()
    })
  })

  test.describe('run-filtered view', () => {
    test.beforeEach(async ({ page }) => {
      await mockBackendApis(page)
    })

    test('shows category tabs when run param present', async ({ page }) => {
      const listings = new ListingsPage(page)
      await listings.goto({ run: MOCK_SEARCH_RUN.id })

      await expect(page.getByRole('tab', { name: 'Great matches' })).toBeVisible()
      await expect(page.getByRole('tab', { name: 'Worth a look' })).toBeVisible()
      await expect(page.getByRole('tab', { name: 'Near misses' })).toBeVisible()
      await expect(page.getByRole('tab', { name: 'Filtered out' })).toBeVisible()
    })

    test('great_match tab is active by default', async ({ page }) => {
      const listings = new ListingsPage(page)
      await listings.goto({ run: MOCK_SEARCH_RUN.id })

      await expect(page.getByRole('tab', { name: 'Great matches' })).toHaveAttribute(
        'aria-selected',
        'true',
      )
    })

    test('switching category tab updates results', async ({ page }) => {
      const listings = new ListingsPage(page)
      await listings.goto({ run: MOCK_SEARCH_RUN.id })

      await page.getByRole('tab', { name: 'Near misses' }).click()
      await expect(page).toHaveURL(/category=near_miss/)
    })

    test('shows link to open run report', async ({ page }) => {
      const listings = new ListingsPage(page)
      await listings.goto({ run: MOCK_SEARCH_RUN.id })

      await expect(page.getByRole('link', { name: 'Open run report' })).toBeVisible()
    })

    test('clear run filter link returns to all listings', async ({ page }) => {
      const listings = new ListingsPage(page)
      await listings.goto({ run: MOCK_SEARCH_RUN.id })

      await page.getByRole('link', { name: 'Clear run filter' }).click()
      await expect(page).toHaveURL('/listings')
    })
  })
})
