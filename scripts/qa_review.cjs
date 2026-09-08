// Shared checks for the static, offline review questions in lecture HTML.
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");

module.exports = async function checkReview(page, stem) {
  const data = JSON.parse(fs.readFileSync(path.join(__dirname,
    "../docs/learning/assets/lecture-qa.json"), "utf8"));
  const lecture = data.lectures.find(item => item.stem === stem);
  const cards = page.locator("#review-qa .qa-item");
  assert.equal(await cards.count(), lecture.items.length);
  assert.equal(await page.locator("#review-qa details[open]").count(), 0);
  const first = cards.first();
  await first.locator("summary").focus();
  await page.keyboard.press("Enter");
  assert.equal(await first.locator("details").getAttribute("open"), "");
  await page.keyboard.press("Enter");
  assert.equal(await first.locator("details").getAttribute("open"), null);
  await page.locator("#review-qa details").evaluateAll(nodes => {
    nodes.forEach(node => { node.open = true; });
  });
  for (const [i, item] of lecture.items.entries()) {
    const text = await cards.nth(i).innerText();
    for (const key of ["q", "a", "e", "formula"]) {
      if (item[key]) assert.ok(text.includes(item[key]), `${stem}, question ${i + 1}: ${key}`);
    }
  }
};
