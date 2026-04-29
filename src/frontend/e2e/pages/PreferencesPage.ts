import { Page, Locator } from '@playwright/test'

export class PreferencesPage {
  readonly page: Page
  readonly heading: Locator
  readonly cityInput: Locator
  readonly saveBtn: Locator
  readonly openRouterKeyInput: Locator

  constructor(page: Page) {
    this.page = page
    this.heading = page.getByRole('heading', { name: /Preferences/i })
    this.cityInput = page.getByLabel(/City/i)
    this.saveBtn = page.getByRole('button', { name: /Save/i })
    this.openRouterKeyInput = page.getByLabel(/OpenRouter API key/i)
  }

  async goto() {
    await this.page.goto('/preferences')
  }
}
