// 无头浏览器实测：三个序章进入灰桥 + 两条路线打到结局；截图到 /workspace/wuzhongcheng-shots/v2-*.png
const { chromium } = require("/workspace/tools-site/scripts/node_modules/playwright");
const BASE = process.env.BASE || "http://127.0.0.1:8766/";
const OUT = "/workspace/wuzhongcheng-shots";
const LEAK = /〔|〕|`|\*\*|→|\bDC\b|[A-Z]{1,4}-[A-Z0-9]{2,}|\b(INS|STR|DEX|CON|CHA|WIL)\b|你决定：|undefined|null|NaN|\{|\}|\$\{|玩家|检定/;
const AVOID = /坚持走下去，绝不回头|回到标题/;
const leaks = [];

async function newGame(page, pc) {
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.evaluate(() => localStorage.clear());
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForFunction(() => window.WZC && window.WZC.nodes);
  await page.evaluate(() => window.WZC.setRng(() => 0.93)); // 偏高的骰子，保证路线推进
  await page.click("#btn-new");
  await page.click(`.char-card[data-pc="${pc}"]`);
  await page.waitForSelector("#screen-game.active #choices .choice");
}
async function scan(page, tag) {
  const txt = await page.evaluate(() => document.querySelector("#screen-game").innerText);
  const m = txt.match(LEAK);
  if (m) {
    const i = txt.indexOf(m[0]);
    leaks.push(`${tag}: “${m[0]}” … ${txt.slice(Math.max(0, i - 30), i + 30).replace(/\n/g, " ")}`);
  }
}
async function play(page, pc, stopIf, shots, maxSteps = 900, avoidNext = null) {
  const used = {}; let steps = 0; const path = [];
  while (steps++ < maxSteps) {
    const node = await page.evaluate(() => window.WZC.state && window.WZC.state.node);
    if (!node) throw new Error("state lost");
    await scan(page, `${pc}@${node}`);
    if (shots[node]) { await page.waitForTimeout(700); await page.screenshot({ path: `${OUT}/${shots[node]}`, fullPage: true }); delete shots[node]; }
    if (path[path.length - 1] !== node) path.push(node);
    if (stopIf(node, await page.evaluate(() => window.WZC.state))) return { node, steps, path };
    const opts = await page.$$eval("#screen-game.active #choices .choice:not([disabled])", (bs) => bs.map((b) => ({ cid: b.dataset.cid, label: b.querySelector(".label").innerText })));
    if (!opts.length) throw new Error(`no choices at ${node}`);
    const nexts = await page.evaluate(([node, cids]) => {
      const n = window.WZC.nodes[node], out = {};
      const all = []; const walk = (l) => (l || []).forEach((c) => { all.push(c); walk(c.sub); });
      walk(n.choices); for (const cid of cids) { const c = all.find((x) => x.id === cid); out[cid] = c ? [c.next, c.success && c.success.next, c.call].filter(Boolean).join(" ") : ""; }
      return out;
    }, [node, opts.map((o) => o.cid)]);
    let best = null, bestScore = 1e9;
    opts.forEach((o, i) => {
      const k = node + "|" + o.cid;
      let sc = (used[k] || 0) * 10 + i * 0.01;
      if (AVOID.test(o.label)) sc += 1000;
      if (/FAIL-/.test(nexts[o.cid])) sc += 500;
      if (avoidNext && avoidNext.test(nexts[o.cid])) sc += 300;
      if (sc < bestScore) { bestScore = sc; best = o; }
    });
    used[node + "|" + best.cid] = (used[node + "|" + best.cid] || 0) + 1;
    await page.click(`#screen-game.active #choices .choice[data-cid="${best.cid}"]`);
    await page.waitForTimeout(15);
  }
  throw new Error(`${pc}: step limit; last path ${path.slice(-15).join(" > ")}`);
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1100, height: 900 } });
  page.on("pageerror", (e) => leaks.push("JS error: " + e.message));
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForTimeout(700); await page.screenshot({ path: `${OUT}/v2-00-title.png` });
  const res = {};
  const toTown = (n) => /^A1-TOWN/.test(n);
  for (const pc of ["edric", "liriel", "thorin"]) {
    await newGame(page, pc);
    const shots = { edric: { "E-PRO-01": "v2-edric-01.png" }, liriel: { "L-PRO-01": "v2-liriel-L-PRO-01-hub.png", "L-PRO-03": "v2-liriel-L-PRO-03-bran.png" }, thorin: { "T-PRO-01": "v2-thorin-01.png" } }[pc];
    const r = await play(page, pc, toTown, shots, 400);
    await page.waitForTimeout(700); await page.screenshot({ path: `${OUT}/v2-${pc}-greybridge.png`, fullPage: true });
    res[pc + " prologue"] = r;
    console.log(pc, "→", r.node, "in", r.steps, "steps:", r.path.join(" > "));
    if (pc !== "thorin") {
      const isEnd = (n, s) => s && s.ended;
      const r2 = await play(page, pc, isEnd, { "CITY-HUB": `v2-${pc}-city.png`, "A2-MINE-01": `v2-${pc}-mine.png`, "A3-SHRINE-07": `v2-${pc}-finale.png` }, 900,
        pc === "liriel" ? /CITY-01|END-CURE/ : null);
      await page.waitForTimeout(700); await page.screenshot({ path: `${OUT}/v2-${pc}-ending.png`, fullPage: true });
      console.log(pc, "ENDING", r2.node, "in", r2.steps, "steps:", r2.path.join(" > "));
    }
  }
  // 额外：L-PRO-03 点进布兰的子选项
  await browser.close();
  console.log("LEAKS/ERRORS:", leaks.length);
  for (const l of leaks.slice(0, 40)) console.log("  ", l);
})().catch((e) => { console.error(e); process.exit(1); });
