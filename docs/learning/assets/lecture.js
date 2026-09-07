"use strict";
(() => {
  const theme = document.getElementById("theme");
  function setTheme(value) {
    if (value === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.dataset.theme = value;
    theme.value = value;
    try { localStorage.setItem("mech-lecture-theme", value); } catch (_) { /* Optional. */ }
  }
  let saved = "system";
  try { saved = localStorage.getItem("mech-lecture-theme") || "system"; } catch (_) { /* Optional. */ }
  setTheme(["system", "light", "dark"].includes(saved) ? saved : "system");
  theme.addEventListener("change", () => setTheme(theme.value));

  const data = window.MECH_LECTURE_DATA;
  const overall = document.getElementById("overall");
  if (!data || data.schema_version !== 1) {
    overall.textContent = "比較データを読み込めません。Markdown版の表を参照してください。";
    document.querySelectorAll(".controls input,.controls button").forEach(el => { el.disabled = true; });
    return;
  }
  const baseline = data.scenarios["30:3"];
  const thickness = document.getElementById("thickness");
  const width = document.getElementById("width");
  const tableBody = document.querySelector("#results tbody");
  const ratioRows = document.getElementById("ratio-rows");
  const definitions = [
    ["root_stress", "公称曲げ応力", 1e-6, "MPa", 3],
    ["tip_deflection", "先端たわみ", 1000, "mm", 4],
    ["first_frequency", "一次固有振動数", 1, "Hz", 2],
    ["tip_temperature", "先端温度", 1, "K", 2],
  ];
  function row(label, ratio) {
    const element = document.createElement("div"); element.className = "ratio-row";
    const name = document.createElement("span"); name.className = "ratio-label"; name.textContent = label;
    const track = document.createElement("div"); track.className = "track"; track.setAttribute("aria-hidden", "true");
    const bar = document.createElement("span"); bar.className = "bar"; bar.style.width = `${ratio / 8 * 100}%`; track.append(bar);
    const value = document.createElement("span"); value.className = "ratio-number"; value.textContent = `${ratio.toFixed(2)}倍`;
    element.append(name, track, value); return element;
  }
  function update() {
    const t = Number(thickness.value), b = Number(width.value);
    const scenario = data.scenarios[`${b}:${t}`];
    document.getElementById("thickness-label").textContent = `${t.toFixed(1)} mm`;
    document.getElementById("width-label").textContent = `${b} mm`;
    const failed = Object.values(scenario.metrics).filter(m => m.status === "fail").length;
    overall.textContent = failed
      ? `総合：制約違反（${failed}指標）。別途 ${scenario.unevaluated_count}分野が未評価。`
      : `総合：未完了。評価した4指標は合格、${scenario.unevaluated_count}分野が未評価。`;
    overall.classList.toggle("failed", failed > 0);
    document.getElementById("mass").textContent = `質量 ${(scenario.mass_kg * 1000).toFixed(2)} g ／ 基準 ${(baseline.mass_kg * 1000).toFixed(2)} g（上限未設定）`;
    const rect = document.getElementById("current-section");
    rect.setAttribute("width", b * 8); rect.setAttribute("height", t * 8); rect.setAttribute("y", 110 - t * 4);
    document.getElementById("section-label").textContent = `幅${b} mm × 厚み${t.toFixed(1)} mm`;
    tableBody.replaceChildren();
    for (const [key, label, scale, unit, digits] of definitions) {
      const metric = scenario.metrics[key], base = baseline.metrics[key];
      const tr = document.createElement("tr"); tr.dataset.metric = key;
      const values = [label, `${(base.value * scale).toFixed(digits)} ${unit}`,
        `${(metric.value * scale).toFixed(digits)} ${unit}`, `${metric.relation} ${(metric.limit * scale).toFixed(digits)} ${unit}`,
        metric.status === "pass" ? "合格" : "違反"];
      values.forEach((text, i) => {
        const cell = document.createElement(i === 0 ? "th" : "td");
        cell.textContent = text; if (i === 0) cell.scope = "row";
        if (i === 4) cell.className = metric.status;
        tr.append(cell);
      });
      tableBody.append(tr);
    }
    const temperatureBase = data.baseline_input.thermal.base_temperature_k;
    ratioRows.replaceChildren(
      row("質量", scenario.mass_kg / baseline.mass_kg),
      row("公称曲げ応力", scenario.metrics.root_stress.value / baseline.metrics.root_stress.value),
      row("先端たわみ", scenario.metrics.tip_deflection.value / baseline.metrics.tip_deflection.value),
      row("一次固有振動数", scenario.metrics.first_frequency.value / baseline.metrics.first_frequency.value),
      row("温度上昇", (scenario.metrics.tip_temperature.value - temperatureBase) /
        (baseline.metrics.tip_temperature.value - temperatureBase)),
    );
  }
  thickness.addEventListener("input", update); width.addEventListener("input", update);
  document.getElementById("thin").addEventListener("click", () => { thickness.value = "2"; width.value = "30"; update(); });
  document.getElementById("reset").addEventListener("click", () => { thickness.value = "3"; width.value = "30"; update(); });
  update();
})();
