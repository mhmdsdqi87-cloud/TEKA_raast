#!/usr/bin/env node
/**
 * RAAST browser validation suite.
 *
 * Real Chromium checks against a real page. Distinguishes:
 *  - automated failures (hard assertions)
 *  - manual-review findings (heuristics, reported not failed)
 *  - not-automatable checks (listed, never claimed)
 *
 * Usage:
 *   node tests/rtl.spec.mjs [--target <url|file://>] [--label <name>]
 *   [--viewports 390,768,1440] [--output-prefix results/run]
 *
 * Exit code 1 when any automated check fails.
 */
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const argv = process.argv.slice(2);
function arg(name, fallback) {
  const i = argv.indexOf(name);
  return i >= 0 ? argv[i + 1] : fallback;
}

const HERE = dirname(fileURLToPath(import.meta.url));
const TARGET = arg("--target", "file://" + resolve(HERE, "../demo/index.html"));
const LABEL = arg("--label", new URL(TARGET).pathname.split("/").pop() || "page");
const VIEWPORTS = (arg("--viewports", "390,768,1440"))
  .split(",").map((v) => parseInt(v.trim(), 10)).filter(Boolean);
const OUT_PREFIX = arg("--output-prefix", null);

const TAP_TARGET_MIN = 40; // px, slight tolerance below the 44px guidance

async function withPage(browser, viewport, fn) {
  const page = await browser.newPage({ viewport: { width: viewport, height: 900 } });
  const result = await fn(page);
  await page.close();
  return result;
}

async function collect(browser, viewport) {
  return withPage(browser, viewport, async (page) => {
    await page.goto(TARGET, { waitUntil: "networkidle" });
    await page.waitForTimeout(600); // fonts settle
    return page.evaluate((tapMin) => {
      const out = { checks: [], manual: [] };
      const add = (id, status, detail) => out.checks.push({ id, status, detail });

      const doc = document.documentElement;
      const dir = doc.getAttribute("dir");
      const lang = doc.getAttribute("lang");
      add("html-dir", dir === "rtl" ? "pass" : "fail", `dir=${dir}`);
      add("html-lang", lang ? "pass" : "fail", `lang=${lang}`);
      add(
        "computed-direction",
        getComputedStyle(document.body).direction === "rtl" ? "pass" : "fail",
        "body computed direction"
      );

      // horizontal overflow
      const sc = document.scrollingElement;
      const overflow = sc.scrollWidth - sc.clientWidth;
      add("no-horizontal-overflow", overflow <= 2 ? "pass" : "fail", `${overflow}px overflow`);

      // body line-height (typography sanity for Arabic script)
      const lh = parseFloat(getComputedStyle(document.body).lineHeight);
      const fs = parseFloat(getComputedStyle(document.body).fontSize);
      const ratio = fs > 0 ? +(lh / fs).toFixed(2) : 0;
      add("body-line-height>=1.5", ratio >= 1.5 ? "pass" : "fail", `ratio=${ratio}`);

      // images have alt
      const imgs = [...document.querySelectorAll("img")];
      const noAlt = imgs.filter((i) => i.getAttribute("alt") === null);
      add("img-alt", noAlt.length === 0 ? "pass" : "fail",
        noAlt.length ? `${noAlt.length} img without alt` : `${imgs.length} img checked`);

      // icon-only buttons have accessible names
      const btns = [...document.querySelectorAll("button")];
      const unnamed = btns.filter(
        (b) => !b.textContent.trim() && !b.getAttribute("aria-label") && !b.getAttribute("title")
      );
      add("icon-button-names", unnamed.length === 0 ? "pass" : "fail",
        unnamed.length ? `${unnamed.length} unnamed buttons` : `${btns.length} buttons checked`);

      // tap targets at this viewport (interactive elements)
      const small = [];
      for (const el of [...document.querySelectorAll("button, a[href]")].slice(0, 60)) {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        const style = getComputedStyle(el);
        if (style.visibility === "hidden" || style.display === "none") continue;
        if (r.height < tapMin) small.push(`${(el.textContent || el.getAttribute("aria-label") || "el").trim().slice(0, 20)}=${Math.round(r.height)}px`);
      }
      add("tap-targets>=40px", small.length === 0 ? "pass" : "fail",
        small.length ? small.slice(0, 4).join(", ") : "all measured targets ok");

      // mixed-direction atoms isolation (manual review signal, not auto-fail)
      const atoms = [...document.querySelectorAll("bdi, [dir=\"ltr\"]")].length;
      const proseHasLatin = /[A-Za-z0-9$@]/.test(document.body.innerText.match(/[^\u0600-\u06FF\s]+/g)?.join("") || "");
      if (atoms > 0) {
        out.manual.push(`bidi: ${atoms} isolated atom(s) found — verify visually at each viewport`);
      } else if (proseHasLatin) {
        out.manual.push("bidi: Latin/digits visible in prose but no isolation markup — review phone/URL/price nodes");
      }

      // form labels
      const inputs = [...document.querySelectorAll("input:not([type=hidden]), textarea, select")];
      const unlabeled = inputs.filter((inp) => {
        if (inp.getAttribute("aria-label") || inp.getAttribute("aria-labelledby")) return false;
        const id = inp.getAttribute("id");
        return !(id && document.querySelector(`label[for="${CSS.escape(id)}"]`));
      });
      if (inputs.length) {
        add("input-labels", unlabeled.length === 0 ? "pass" : "fail",
          unlabeled.length ? `${unlabeled.length} unlabeled controls` : `${inputs.length} controls labeled`);
      }

      // keyboard reachability smoke: focus first interactive element
      const focusables = [...document.querySelectorAll("a[href], button, input, [tabindex='0']")];
      if (focusables.length) {
        const before = document.activeElement;
        focusables[0].focus();
        add("keyboard-focus", document.activeElement !== before && document.activeElement === focusables[0] ? "pass" : "fail",
          "first focusable receives focus");
      }

      // not automatable (honest list)
      out.notAutomatable = [
        "glyph rendering fidelity (font rasterization differs per OS)",
        "bidi reordering correctness of complex mixed strings (needs human reading)",
        "kashida/justification aesthetics",
        "color contrast inside images",
      ];
      return out;
    }, TAP_TARGET_MIN);
  });
}

const browser = await chromium.launch();
const perViewport = [];
const shotsDir = resolve(HERE, "../results/screenshots");
mkdirSync(shotsDir, { recursive: true });

for (const vp of VIEWPORTS) {
  const data = await collect(browser, vp);
  await withPage(browser, vp, async (page) => {
    await page.goto(TARGET, { waitUntil: "networkidle" });
    await page.waitForTimeout(400);
    await page.screenshot({ path: `${shotsDir}/${LABEL}-${vp}.png`, fullPage: false });
    await page.screenshot({ path: `${shotsDir}/${LABEL}-${vp}-full.png`, fullPage: true });
  });
  perViewport.push({ viewport: vp, ...data });
  const failed = data.checks.filter((c) => c.status === "fail").length;
  console.log(`viewport ${vp}px: ${data.checks.filter((c) => c.status === "pass").length} pass, ${failed} fail, ${data.manual.length} manual`);
}
await browser.close();

const report = {
  tool: "raast-browser",
  target: TARGET,
  label: LABEL,
  generatedAt: new Date().toISOString(),
  viewports: perViewport,
  limitations: [
    "DOM/computed-style checks approximate visual truth; screenshots are attached for human review.",
    "Font rasterization and bidi shaping are platform-dependent; run on target platforms for full confidence.",
  ],
};

const failedTotal = perViewport.reduce(
  (n, v) => n + v.checks.filter((c) => c.status === "fail").length, 0);

let md = `# RAAST Browser Report — ${LABEL}\n\nTarget: \`${TARGET}\`\nGenerated: ${report.generatedAt}\n\n`;
for (const v of perViewport) {
  md += `## ${v.viewport}px\n\n| Check | Status | Detail |\n|---|---|---|\n`;
  for (const c of v.checks) md += `| ${c.id} | ${c.status} | ${c.detail} |\n`;
  if (v.manual.length) { md += `\n**Manual review:**\n${v.manual.map((m) => `- ${m}`).join("\n")}\n`; }
  md += `\nNot automatable: ${v.notAutomatable.join("; ")}\n\n`;
}

if (OUT_PREFIX) {
  const p = resolve(HERE, "..", OUT_PREFIX);
  mkdirSync(dirname(p), { recursive: true });
  writeFileSync(p + ".json", JSON.stringify(report, null, 2));
  writeFileSync(p + ".md", md);
  console.log(`wrote ${OUT_PREFIX}.json / .md`);
} else {
  console.log(md);
}
process.exit(failedTotal > 0 ? 1 : 0);
