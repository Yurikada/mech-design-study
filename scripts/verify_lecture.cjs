// Optional visual QA: run in a Node environment with Playwright available.
// BROWSER_EXECUTABLE may point to an installed Chromium/Edge executable.
// JAPANESE_PAGE_AUDIT may point to the local japanese-page-design skill audit.js.
const { chromium } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const assert = require("node:assert/strict");

const root = path.resolve(__dirname, "..");
const output = path.join(root, "outputs", "lecture-qa");
fs.mkdirSync(output, { recursive: true });
const dataText = fs.readFileSync(path.join(root, "docs/learning/assets/lecture-data.js"), "utf8");
const data = JSON.parse(dataText.split("window.MECH_LECTURE_DATA = ")[1].trim().slice(0, -1));
const url = pathToFileURL(path.join(root, "docs/learning/01-lecture.html")).href;
const fields = [
  ["root_stress", 1e-6, "MPa", 3], ["tip_deflection", 1000, "mm", 4],
  ["first_frequency", 1, "Hz", 2], ["tip_temperature", 1, "K", 2],
];

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
  const context = await browser.newContext();
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("requestfailed", request => errors.push(request.url()));
  const measurements = [];
  try {
    await page.goto(url);
    for (const [key, scenario] of Object.entries(data.scenarios)) {
      const [width, thickness] = key.split(":");
      await page.locator("#width").fill(width);
      await page.locator("#thickness").fill(thickness);
      for (const [field, scale, unit, digits] of fields) {
        const cells = await page.locator(`tr[data-metric="${field}"]`).locator("td").allTextContents();
        assert.equal(cells[1], `${(scenario.metrics[field].value * scale).toFixed(digits)} ${unit}`);
        assert.equal(cells[3], scenario.metrics[field].status === "pass" ? "合格" : "違反");
      }
      assert.match(await page.locator("#overall").innerText(), /9分野が未評価/);
    }
    await page.locator("#thin").click();
    assert.equal(await page.locator("#thickness").inputValue(), "2");
    assert.match(await page.locator("#overall").innerText(), /2指標/);
    await page.locator("#reset").click();
    assert.equal(await page.locator("#thickness").inputValue(), "3");
    assert.equal(await page.locator("#width").inputValue(), "30");

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
          assert.equal(result.width, result.scrollWidth, "Page overflow");
          assert.deepEqual(result.imageErrors, []);
          if (process.env.JAPANESE_PAGE_AUDIT) {
            const source = fs.readFileSync(process.env.JAPANESE_PAGE_AUDIT, "utf8");
            result.japaneseAudit = await page.evaluate(async (source) => {
              const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
              return JSON.parse(await new AsyncFunction(source.replace(/\nJSON\.stringify\(/, "\nreturn JSON.stringify("))());
            }, source);
            assert.equal(result.japaneseAudit.ok, true, JSON.stringify(result.japaneseAudit));
          }
          measurements.push({ width, scheme, theme, ...result });
        }
      }
    }
    await page.setViewportSize({ width: 1280, height: 1000 });
    await page.locator("#theme").selectOption("light");
    await page.locator('img[src="assets/cantilever.svg"]').screenshot({ path: path.join(output, "cantilever.png") });
    await page.screenshot({ path: path.join(output, "lecture-desktop.png"), fullPage: true });
    await page.locator("#experiment").screenshot({ path: path.join(output, "comparison-desktop.png") });
    await page.setViewportSize({ width: 320, height: 900 });
    await page.locator("#theme").selectOption("dark");
    await page.locator("#conditions").screenshot({ path: path.join(output, "conditions-mobile-dark.png") });
    await page.locator("#experiment").screenshot({ path: path.join(output, "comparison-mobile-dark.png") });

    const svgMeasurements = [];
    for (const name of ["cantilever", "heat-path", "evaluation-flow", "verification-validation"]) {
      await page.goto(pathToFileURL(path.join(root, `docs/learning/assets/${name}.svg`)).href);
      const clipped = await page.evaluate(() => {
        const view = document.documentElement.viewBox.baseVal;
        return [...document.querySelectorAll("text")].map(el => ({ text: el.textContent, box: el.getBBox() }))
          .filter(({box}) => box.x < 0 || box.y < 0 || box.x + box.width > view.width || box.y + box.height > view.height)
          .map(({text}) => text);
      });
      assert.deepEqual(clipped, [], `SVG label clipping: ${name}`);
      svgMeasurements.push({name, clipped});
    }
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, "audit.json"), JSON.stringify({scenarios: 36, measurements, svgMeasurements, errors}, null, 2));
    console.log("36 scenarios, 18 viewport/theme combinations and 4 SVG bounds checks passed.");
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
