import { test, expect } from "@playwright/test";

/**
 * Smoke tests: verify critical user flows render without crashing.
 * These require the full stack running (docker compose up).
 * Run with: npx playwright test
 */

const BASE = process.env.BASE_URL || "http://localhost:3000";

test.describe("Catalog", () => {
  test("loads catalog page with instruments", async ({ page }) => {
    await page.goto(BASE);
    await expect(page.locator("h1")).toContainText("Catalog");
    // Should have at least one instrument link.
    const links = page.locator('a[href^="/instruments/"]');
    await expect(links.first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Product Page", () => {
  test("renders price chart and forecast data", async ({ page }) => {
    await page.goto(BASE);
    // Click first instrument.
    const firstLink = page.locator('a[href^="/instruments/"]').first();
    await firstLink.click();
    // Should show product name and forecast section.
    await expect(page.locator("h1")).toBeVisible();
    await expect(page.locator("text=Price & Forecast")).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Scanner", () => {
  test("loads scanner with ranked instruments", async ({ page }) => {
    await page.goto(`${BASE}/scanner`);
    await expect(page.locator("h1")).toContainText("Scanner");
    // Table should render rows.
    await expect(page.locator("table tbody tr").first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Dashboard", () => {
  test("loads dashboard with KPIs", async ({ page }) => {
    await page.goto(`${BASE}/dashboard`);
    await expect(page.locator("h1")).toContainText("Dashboard");
    await expect(page.locator("text=Portfolio Value")).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Grade Tab", () => {
  test("loads grade page with search", async ({ page }) => {
    await page.goto(`${BASE}/grade`);
    // Should have a search input.
    const input = page.locator('input[type="text"]').first();
    await expect(input).toBeVisible();
  });
});

test.describe("Market Overview", () => {
  test("loads market page with breadth stats", async ({ page }) => {
    await page.goto(`${BASE}/market`);
    await expect(page.locator("h1")).toContainText("Market Overview");
    await expect(page.locator("text=Breadth")).toBeVisible({ timeout: 10000 });
  });
});

test.describe("AI Assistant", () => {
  test("chat dock opens and accepts input", async ({ page }) => {
    await page.goto(BASE);
    // Click the chat bubble.
    const bubble = page.locator('button[aria-label="Open AI assistant"]');
    await bubble.click();
    // Chat panel should appear.
    await expect(page.locator("text=Research Assistant")).toBeVisible();
    // Should have input field.
    const input = page.locator('input[placeholder="Ask about instruments..."]');
    await expect(input).toBeVisible();
  });
});
