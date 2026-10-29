#!/usr/bin/env node
/** Phase 1 live UI: HUD 390px, bag equip, dossier, container continuation */
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const http = require("http");
const { spawn } = require("child_process");

const ROOT = path.join(__dirname, "..", "public");
const OUT = path.join(__dirname, "..", "shots", "phase1");
fs.mkdirSync(OUT, { recursive: true });
const PORT = 8793;
const BASE = `http://127.0.0.1:${PORT}/`;

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

async function unlock(page) {
  await page.addInitScript(() => {
    try { sessionStorage.setItem("wzc_gate_unlocked", "test"); } catch (_) {}
  });
}

async function startGame(page, pc) {
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.evaluate(() => { try { localStorage.clear(); } catch (_) {} });
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForFunction(() => window.WZC && window.WZC.nodes);
  await page.click("#btn-new");
  await page.click(`.char-card[data-pc="${pc}"]`);
  await page.waitForSelector("#screen-game.active #choices .choice");
}

async function jumpTo(page, nodeId, extraVars = {}) {
  await page.evaluate(([nodeId, extraVars]) => {
    const s = window.WZC.state;
    Object.assign(s.vars, extraVars);
    s.node = nodeId;
    s.seen[nodeId] = true;
    s.pending = null;
  }, [nodeId, extraVars]);
  // force repaint via choosing a noop — call paint through WZC by re-entering
  await page.evaluate((nodeId) => {
    const s = window.WZC.state;
    const out = { toasts: [], blocks: [] };
    window.WZCEngine.enter(s, nodeId, out);
    // trigger UI
    document.getElementById("btn-journal").click();
    document.getElementById("modal-close").click();
  }, nodeId);
  // harder repaint: use WZC hooks — dispatch by clicking menu close then...
  await page.evaluate(() => {
    // main.js paint is closed; simulate by reloading state via continue path
    const s = window.WZC.state;
    // expose temporary paint by clicking a choice if any, else rebuild via start
  });
}

// Better approach: use engine choose path naturally, or inject paint
async function forcePaint(page) {
  await page.evaluate(() => {
    const s = window.WZC.state;
    if (!s) return;
    const handlers = {
      onChoice(c) {
        const from = s.node;
        const out = window.WZCEngine.choose(s, c, null);
        window.WZCUI.renderGame(s, window.WZC.nodes, window.WZC.meta, {
          view: { label: out.label, blocks: out.blocks, checkText: out.checkText, ok: out.check ? out.check.ok : null },
          toasts: out.toasts,
          sameNode: s.node === from,
        }, handlers);
      },
      onSub(c) {
        const out = window.WZCEngine.chooseSub(s, c);
        if (!out) return;
        window.WZCUI.renderGame(s, window.WZC.nodes, window.WZC.meta, {
          view: { label: out.label, blocks: out.blocks, checkText: out.checkText, ok: out.check ? out.check.ok : null },
          toasts: out.toasts,
          sameNode: true,
        }, handlers);
      },
    };
    window.WZCUI.renderGame(s, window.WZC.nodes, window.WZC.meta, null, handlers);
  });
}

async function setNode(page, nodeId, vars = {}) {
  await page.evaluate(([nodeId, vars]) => {
    const s = window.WZC.state;
    Object.assign(s.vars, vars);
    s.pending = null;
    window.WZCEngine.enter(s, nodeId, { toasts: [], blocks: [] });
  }, [nodeId, vars]);
  await forcePaint(page);
}

(async () => {
  // static server
  const server = http.createServer((req, res) => {
    let url = decodeURIComponent((req.url || "/").split("?")[0]);
    if (url === "/") url = "/index.html";
    const fp = path.join(ROOT, url.replace(/^\//, ""));
    if (!fp.startsWith(ROOT) || !fs.existsSync(fp) || fs.statSync(fp).isDirectory()) {
      res.writeHead(404); res.end("no"); return;
    }
    const ext = path.extname(fp);
    const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".svg": "image/svg+xml", ".mp3": "audio/mpeg", ".ogg": "audio/ogg" };
    res.writeHead(200, { "Content-Type": types[ext] || "application/octet-stream", "Cache-Control": "no-store" });
    fs.createReadStream(fp).pipe(res);
  });
  await new Promise((r) => server.listen(PORT, r));

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  page.on("pageerror", (e) => console.error("PAGEERROR", e.message));
  await unlock(page);

  // 1) HUD mobile
  await startGame(page, "liriel");
  await page.waitForTimeout(200);
  const hud = await page.evaluate(() => {
    const bar = document.getElementById("hud");
    const vitals = [...document.querySelectorAll("#hud-vitals .vital")].map((el) => ({
      id: el.id, text: el.textContent.trim(), empty: !el.textContent.trim(),
      h: el.getBoundingClientRect().height, w: el.getBoundingClientRect().width,
    }));
    const wrap = getComputedStyle(bar).flexDirection;
    const hudH = bar.getBoundingClientRect().height;
    return { wrap, hudH, vitals, name: document.getElementById("hud-name").textContent };
  });
  assert(hud.wrap === "column", "HUD should be column flex");
  assert(hud.vitals.length === 5, "5 vitals");
  assert(hud.vitals.every((v) => !v.empty && v.h > 0 && v.w > 0), "no empty vital chips: " + JSON.stringify(hud.vitals));
  assert(hud.hudH < 160, "HUD should stay compact on mobile, h=" + hud.hudH);
  await page.screenshot({ path: path.join(OUT, "01-hud-mobile.png"), fullPage: false });
  console.log("HUD OK", hud.vitals.map((v) => v.text).join(" | "));

  // help from ?
  await page.click("#btn-help");
  await page.waitForSelector("#modal-body .stats-help");
  const helpTxt = await page.$eval("#modal-body", (el) => el.innerText);
  assert(/战力/.test(helpTxt) && /沉沦/.test(helpTxt) && /共鸣/.test(helpTxt), "stats help content");
  await page.click("#modal-close");

  // 2) Bag equip flow
  const beforePow = await page.evaluate(() => window.WZCEngine.combatPower(window.WZC.state));
  await page.click("#btn-bag");
  await page.waitForSelector("#modal-body .bag-row");
  const bagBefore = await page.evaluate(() => document.getElementById("modal-body").innerText);
  assert(/装备/.test(bagBefore) && /精灵细剑|银链|旅行布袍/.test(bagBefore), "bag shows gear names: " + bagBefore.slice(0, 200));
  assert(/合计战力|战力/.test(bagBefore), "shows power");
  await page.screenshot({ path: path.join(OUT, "02-bag-before-unequip.png") });
  // unequip weapon
  const unequipBtn = await page.$('#modal-body [data-act="unequip"][data-id="weapon"]');
  assert(unequipBtn, "unequip weapon button");
  await unequipBtn.click();
  await page.waitForTimeout(100);
  const midPow = await page.evaluate(() => window.WZCEngine.combatPower(window.WZC.state));
  assert(midPow === beforePow - 2, `power after unequip ${beforePow} -> ${midPow}`);
  const hudPow = await page.$eval("#hud-power", (el) => el.textContent);
  assert(hudPow.includes(String(midPow)), "HUD power updated: " + hudPow);
  await page.screenshot({ path: path.join(OUT, "03-bag-after-unequip.png") });
  // re-equip
  const equipBtn = await page.$('#modal-body [data-act="equip"][data-id="elf_rapier"]');
  assert(equipBtn, "equip rapier button");
  await equipBtn.click();
  await page.waitForTimeout(100);
  const afterPow = await page.evaluate(() => window.WZCEngine.combatPower(window.WZC.state));
  assert(afterPow === beforePow, "power restored");
  await page.click("#modal-close");
  console.log("BAG/EQUIP OK", beforePow, midPow, afterPow);

  // 3) dossier
  await page.evaluate(() => {
    const s = window.WZC.state;
    s.vars.met_valen = true;
    s.vars.dossier_valen_depth = 1;
    s.vars.met_edric = true;
    s.seen["A1-TOWN-02"] = true;
  });
  await page.click("#btn-people");
  await page.waitForSelector("#modal-body .dossier");
  const people = await page.$eval("#modal-body", (el) => el.innerText);
  assert(/莉瑞尔/.test(people), "PC dossier");
  assert(/外貌|性格|已知/.test(people), "dossier fields");
  assert(/瓦伦|艾德里克/.test(people), "met NPCs listed");
  await page.screenshot({ path: path.join(OUT, "04-dossier.png") });
  await page.click("#modal-close");
  console.log("DOSSIER OK");

  // 4) fall HUD + threshold
  await page.evaluate(() => {
    const s = window.WZC.state;
    const toasts = [];
    window.WZCEngine.apply(s, [{ op: "add", k: "fall", v: 4 }], toasts);
    window.__fallToasts = toasts;
  });
  await forcePaint(page);
  const fallHud = await page.$eval("#hud-fall", (el) => ({ t: el.textContent, c: el.className }));
  assert(/沉 4\/6/.test(fallHud.t), "fall hud " + fallHud.t);
  assert(/warn/.test(fallHud.c), "fall warn class");
  const fallFlag = await page.evaluate(() => !!window.WZC.state.vars.fall_threshold_4);
  assert(fallFlag, "fall_threshold_4 set");
  console.log("FALL HUD OK", fallHud);

  // 5) container continuation at tavern
  await page.evaluate(() => {
    const s = window.WZC.state;
    s.vars.met_edric = true;
    s.vars.shared_fragment_truth = false;
    s.used = {}; // allow recog again
    s.pending = null;
    window.WZCEngine.enter(s, "A1-TOWN-02", { toasts: [], blocks: [] });
    const parent = window.WZC.nodes["A1-TOWN-02"].choices.find((c) => c.id === "t4_li");
    // open parent as pending then choose show
    const open = window.WZCEngine.choose(s, parent, null);
    const sub = parent.sub.find((x) => x.id === "t4_li_show");
    const out = window.WZCEngine.chooseSub(s, sub);
    window.__containerOut = {
      label: out.label,
      texts: (out.blocks || []).map((b) => b.t === "fold" ? ("FOLD:" + b.label + ":" + (b.blocks||[]).map(x=>x.text).join(" ")) : (b.text || "")),
      toasts: (out.toasts || []).map((x) => x.text),
      shared: !!s.vars.shared_fragment_truth,
      showed: !!s.vars.showed_containers,
    };
    window.WZCUI.renderGame(s, window.WZC.nodes, window.WZC.meta, {
      view: { label: out.label, blocks: out.blocks, checkText: out.checkText || "", ok: null },
      toasts: out.toasts,
      sameNode: true,
    }, { onChoice() {}, onSub() {} });
  });
  await page.waitForTimeout(150);
  const cont = await page.evaluate(() => window.__containerOut);
  assert(cont && cont.texts.length >= 3, "container blocks: " + JSON.stringify(cont));
  const joined = cont.texts.join("\n");
  assert(/低鸣|容器/.test(joined), "container core text");
  assert(/秘密|深谈|离境|文书|信任/.test(joined), "follow-up beat: " + joined.slice(0, 240));
  assert(cont.shared && cont.showed, "flags set");
  assert(cont.texts.some((x) => x.startsWith("FOLD:")), "has fold block");
  const resultVisible = await page.$eval("#result", (el) => el.innerText);
  assert(/容器|低鸣/.test(resultVisible), "result panel shows text");
  await page.screenshot({ path: path.join(OUT, "05-container-continuation.png"), fullPage: true });
  console.log("CONTAINER OK", joined.slice(0, 140).replace(/\n/g, " / "));

  // vitals still non-empty after all
  const vitals2 = await page.$$eval("#hud-vitals .vital", (els) => els.map((e) => e.textContent.trim()));
  assert(vitals2.every(Boolean), "vitals still filled: " + vitals2.join("|"));

  await browser.close();
  server.close();
  console.log("ALL PHASE1 UI TESTS PASSED →", OUT);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
