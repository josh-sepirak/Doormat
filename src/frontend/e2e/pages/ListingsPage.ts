import { Page, Locator } from '@playwright/test'

export class ListingsPage {
  readonly page: Page
  readonly heading: Locator
  readonly emptyState: Locator
  readonly listingCards: Locator
  readonly categoryTabs: Locator

  constructor(page: Page) {
    this.page = page
    this.heading = page.getByRole('heading', { name: /Listings/i })
    this.emptyState = page.getByText(/No listings yet/i)
    this.listingCards = page.locator('.rounded-2xl.border').filter({ hasNot: page.locator('nav') })
    this.categoryTabs = page.getByRole('tablist', { name: /Result category/i })
  }

  async goto(params?: Record<string, string>) {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    await this.page.goto(`/listings${qs}`)
  }

  tab(label: string) {
    return this.page.getByRole('tab', { name: label })
  }
}
