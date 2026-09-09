// Optional browser QA, using the same environment as verify_lecture.cjs.
const { chromium } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const assert = require("node:assert/strict");
const checkReview = require("./qa_review.cjs");
const root = path.resolve(__dirname, "..");
const stem = process.argv[2] || "03-fem";
assert.ok(["03-fem", "04-fem-benchmark", "05-mesh-convergence"].includes(stem));
const benchmark = stem !== "03-fem";
const convergence = stem === "05-mesh-convergence";
const output = path.join(root, "outputs", convergence ? "convergence-lecture-qa" : benchmark ? "benchmark-lecture-qa" : "fem-lecture-qa");
fs.mkdirSync(output, { recursive: true });

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("requestfailed", request => errors.push(request.url()));
  const measurements = [];
  try {
    await page.goto(pathToFileURL(path.join(root, `docs/learning/${stem}.html`)).href);
    await checkReview(page, stem);
    const links = await page.locator("a[href]").evaluateAll(elements => elements.map(e => e.getAttribute("href")));
    for (const link of links) {
      if (link.startsWith("#")) assert.equal(await page.locator(link).count(), 1);
      else if (!link.startsWith("https://")) assert.ok(fs.existsSync(path.join(root, "docs/learning", link)));
    }
    for (const width of [320, 768, 1280]) {
      await page.setViewportSize({ width, height: 900 });
      for (const scheme of ["light", "dark"]) {
        await page.emulateMedia({ colorScheme: scheme });
        for (const theme of ["system", "light", "dark"]) {
          await page.locator("#theme").selectOption(theme);
          const result = await page.evaluate(() => ({
            width: document.documentElement.clientWidth,
            scrollWidth: document.documentElement.scrollWidth,
            foreground: getComputedStyle(document.body).color,
            background: getComputedStyle(document.body).backgroundColor,
            imageErrors: [...document.images].filter(i => !i.complete || !i.naturalWidth).map(i => i.src),
          }));
          assert.equal(result.width, result.scrollWidth);
          assert.deepEqual(result.imageErrors, []);
          const dark = theme === "dark" || (theme === "system" && scheme === "dark");
          assert.equal(result.background, dark ? "rgb(16, 27, 33)" : "rgb(250, 250, 247)");
          if (process.env.JAPANESE_PAGE_AUDIT) {
            const source = fs.readFileSync(process.env.JAPANESE_PAGE_AUDIT, "utf8");
            result.japaneseAudit = await page.evaluate(async source => {
              const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
              return JSON.parse(await new AsyncFunction(source.replace(/\nJSON\.stringify\(/, "\nreturn JSON.stringify("))());
            }, source);
            assert.equal(result.japaneseAudit.ok, true, JSON.stringify(result.japaneseAudit));
          }
          measurements.push({ width, scheme, theme, ...result });
        }
      }
    }
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.locator("#theme").selectOption("light");
    await page.screenshot({ path: path.join(output, "desktop.png"), fullPage: true });
    await page.locator(benchmark ? "#model img" : "#choices img").screenshot({ path: path.join(output, "diagram.png") });
    await page.setViewportSize({ width: 320, height: 900 });
    await page.locator("#theme").selectOption("dark");
    await page.locator(benchmark ? "#model" : "#choices").screenshot({ path: path.join(output, "mobile-dark.png") });
    await page.locator(convergence ? "#l5-q01" : benchmark ? "#l4-q06" : "#l3-q23").screenshot({ path: path.join(output, "question-mobile-dark.png") });
    const figure = convergence ? "variable-curvature-study.svg" : benchmark ? "pure-bending-study.svg" : "fem-mesh-and-order.svg";
    await page.goto(pathToFileURL(path.join(root, `docs/learning/assets/${figure}`)).href);
    const clipped = await page.evaluate(() => {
      const view = document.documentElement.viewBox.baseVal;
      return [...document.querySelectorAll("text")].filter(el => {
        const b = el.getBBox();
        return b.x < 0 || b.y < 0 || b.x + b.width > view.width || b.y + b.height > view.height;
      }).map(el => el.textContent);
    });
    assert.deepEqual(clipped, []);
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, "audit.json"), JSON.stringify({ measurements, clipped, errors }, null, 2));
    console.log(`${stem}: 18 viewport/theme checks, Q&A, local links, SVG text bounds passed.`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
