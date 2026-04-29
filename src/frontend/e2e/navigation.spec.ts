import { test, expect } from '@playwright/test'
import { mockBackendApis } from './fixtures/api-mocks'

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await mockBackendApis(page)
  })

  test('header shows Doormat branding and nav links', async ({ page }) => {
    await page.goto('/')
    // Logo link has aria-label="Home"
    await expect(page.getByRole('link', { name: 'Home' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Dashboard' }).first()).toBeVisible()
    await expect(page.getByRole('link', { name: 'Listings' }).first()).toBeVisible()
    await expect(page.getByRole('link', { name: 'Costs' }).first()).toBeVisible()
    await expect(page.getByRole('link', { name: 'Preferences' }).first()).toBeVisible()
  })

  test('navigates to listings page', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('link', { name: 'Listings' }).first().click()
    await expect(page).toHaveURL('/listings')
  })

  test('navigates to preferences via Settings button', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('link', { name: 'Settings' }).click()
    await expect(page).toHaveURL('/preferences')
  })

  test('navigates to preferences via nav link', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('link', { name: 'Preferences' }).first().click()
    await expect(page).toHaveURL('/preferences')
  })

  test('navigates to costs page', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('link', { name: 'Costs' }).first().click()
    await expect(page).toHaveURL('/costs')
  })

  test('logo link returns to dashboard', async ({ page }) => {
    await page.goto('/listings')
    // Logo link has aria-label="Home" (not "Doormat")
    await page.getByRole('link', { name: 'Home' }).click()
    await expect(page).toHaveURL('/')
  })

  test('page title includes Doormat', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveTitle(/Doormat/)
  })
})
