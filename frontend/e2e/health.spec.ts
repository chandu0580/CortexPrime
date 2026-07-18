import { test, expect } from "@playwright/test"

test.describe("Landing page", () => {
  test("loads the app at /", async ({ page }) => {
    await page.goto("/")
    await expect(page).toHaveTitle(/CortexPrime|Prime/)
  })

  test("renders the main heading", async ({ page }) => {
    await page.goto("/")
    const heading = page.locator("h1").first()
    await expect(heading).toBeVisible()
    await expect(heading).not.toBeEmpty()
  })

  test("navigation to /login works", async ({ page }) => {
    await page.goto("/")
    await page.goto("/login")
    await expect(page).toHaveURL(/\/login/)
  })

  test("page body renders without errors", async ({ page }) => {
    await page.goto("/")
    const body = page.locator("body")
    await expect(body).toBeVisible()
    const errors = page.locator("[data-testid=error-boundary]")
    await expect(errors).toHaveCount(0)
  })
})
