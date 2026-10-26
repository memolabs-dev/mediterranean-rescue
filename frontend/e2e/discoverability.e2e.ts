import { expect, test } from "@playwright/test";

// What a search engine, a chat app or a language model reads first. Served by the production
// image (WhiteNoise), so a missing file would come back as the application page, status 200.
const files = [
  { path: "/llms.txt", type: "text/plain", contains: "not the official website of SOS MEDITERRANEE" },
  { path: "/llms-full.txt", type: "text/plain", contains: "/api/v1/events/" },
  { path: "/robots.txt", type: "text/plain", contains: "Disallow: /workspace" },
  { path: "/sitemap.xml", type: "xml", contains: "<loc>https://rescue.memolabs.dev/about</loc>" },
  { path: "/manifest.webmanifest", type: "application/manifest+json", contains: '"name": "Mediterranean Rescue"' },
  { path: "/.well-known/security.txt", type: "text/plain", contains: "Contact: " },
];

test("machine-readable files are served with their own type", async ({ request }) => {
  for (const file of files) {
    const response = await request.get(file.path);
    expect(response.status(), file.path).toBe(200);
    expect(response.headers()["content-type"], file.path).toContain(file.type);
    expect(await response.text(), file.path).toContain(file.contains);
  }
  const sitemap = await (await request.get("/sitemap.xml")).text();
  expect(sitemap, "private pages stay out of the sitemap").not.toMatch(/workspace|invite/);
  for (const image of ["/og-image.png", "/apple-touch-icon.png", "/icon-192.png", "/icon-512.png"]) {
    const response = await request.get(image);
    expect(response.headers()["content-type"], image).toBe("image/png");
  }
});

test("the page carries a canonical address, a link preview and structured data", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", "https://rescue.memolabs.dev/");
  await expect(page.locator('meta[property="og:image"]')).toHaveAttribute("content", "https://rescue.memolabs.dev/og-image.png");
  await expect(page.locator('meta[name="description"]')).toHaveAttribute("content", /independent volunteer project/);
  const ld = JSON.parse((await page.locator('script[type="application/ld+json"]').textContent()) ?? "{}");
  expect(ld["@type"]).toBe("WebApplication");
  expect(ld.license).toBe("https://opensource.org/licenses/MIT");
});
