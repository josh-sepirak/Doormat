import { test, expect } from '@playwright/test'
import { mockBackendApis } from './fixtures/api-mocks'

test.describe('Costs page', () => {
  test.beforeEach(async ({ page }) => {
    await mockBackendApis(page)
  })

  test('shows AI spending heading', async ({ page }) => {
    await page.goto('/costs')
    await expect(page.getByRole('heading', { name: /AI spending/i })).toBeVisible()
  })

  test('shows total cost', async ({ page }) => {
    await page.goto('/costs')
    await expect(page.getByText(/\$0\.004/)).toBeVisible()
  })

  test('shows model breakdown', async ({ page }) => {
    await page.goto('/costs')
    await expect(page.getByText(/gpt-4o-mini/i)).toBeVisible()
  })
})
