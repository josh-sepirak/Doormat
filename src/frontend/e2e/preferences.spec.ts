import { test, expect } from '@playwright/test'
import { mockBackendApis } from './fixtures/api-mocks'

test.describe('Preferences page', () => {
  test.beforeEach(async ({ page }) => {
    await mockBackendApis(page)
  })

  test('shows Preferences heading', async ({ page }) => {
    await page.goto('/preferences')
    await expect(page.getByRole('heading', { name: /Preferences/i })).toBeVisible()
  })

  test('shows existing city value', async ({ page }) => {
    await page.goto('/preferences')
    // City field is an <input> — wait for it to populate from API
    const cityInput = page.getByLabel('City')
    await expect(cityInput).toHaveValue('Austin, TX')
  })

  test('shows description value', async ({ page }) => {
    await page.goto('/preferences')
    const descInput = page.getByLabel('Description')
    await expect(descInput).toHaveValue('Looking for a 2BR near downtown')
  })

  test('shows API Configuration section in AI & API Keys tab', async ({ page }) => {
    await page.goto('/preferences')
    await page.getByRole('button', { name: /AI & API Keys/i }).click()
    await expect(page.getByText('API Configuration', { exact: true })).toBeVisible()
  })

  test('can navigate back to dashboard from preferences', async ({ page }) => {
    await page.goto('/preferences')
    await page.getByRole('link', { name: 'Dashboard' }).first().click()
    await expect(page).toHaveURL('/')
  })
})
