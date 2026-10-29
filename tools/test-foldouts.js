#!/usr/bin/env node
/** Foldout explicit-prose checklist: surface stays tame; fold blocks hold explicit beats. */
const fs = require("fs");
const path = require("path");
const N = JSON.parse(fs.readFileSync(path.join(__dirname, "../public/data/nodes.json"), "utf8"));

function walkBlocks(blocks, fn) {
  for (const b of blocks || []) {
    fn(b);
    if (b.t === "fold") walkBlocks(b.blocks, fn);
  }
}
function allBlocks(n) {
  const out = [];
  walkBlocks(n.blocks, (b) => out.push(b));
  const stack = [...(n.choices || [])];
  while (stack.length) {
    const c = stack.pop();
    walkBlocks(c.result, (b) => out.push(b));
    for (const br of ["success", "fail"]) if (c[br]) walkBlocks(c[br].result, (b) => out.push(b));
    stack.push(...(c.sub || []));
  }
  return out;
}
function surfaceText(n) {
  const parts = [];
  const collect = (blocks) => {
    for (const b of blocks || []) {
      if (b.t === "fold") continue;
      if (b.text) parts.push(b.text);
    }
  };
  collect(n.blocks);
  const stack = [...(n.choices || [])];
  while (stack.length) {
    const c = stack.pop();
    collect(c.result);
    for (const br of ["success", "fail"]) if (c[br]) collect(c[br].result);
    stack.push(...(c.sub || []));
  }
  return parts.join("\n");
}
function foldText(n) {
  return allBlocks(n).filter((b) => b.t === "fold").map((b) => JSON.stringify(b.blocks || b.text || "")).join("\n");
}

let failed = 0;
function fail(msg) { console.error("FAIL:", msg); failed++; }

// Nodes that must have at least one fold
const NEED_FOLD = [
  "L-PRO-07", "L-PRO-08", "L-PRO-06", "L-PRO-02",
  "R-DES-01", "R-DES-03", "R-DES-06",
  "A1-TOWN-04", "D-ALT", "A1-TOWN-02",
];
for (const nid of NEED_FOLD) {
  const folds = allBlocks(N[nid] || {}).filter((b) => b.t === "fold");
  if (!folds.length) fail(`${nid} missing fold block`);
}

// Gate guard: surface must not dump the full sex scene; fold must have it
const g = N["L-PRO-08"];
const gSurf = surfaceText(g);
const gFold = foldText(g);
if (/自己坐下去吃进/.test(gSurf)) fail("L-PRO-08 surface still has full sex beat");
if (!/自己坐下去吃进/.test(gFold)) fail("L-PRO-08 fold missing explicit beat");
if (!/纪律处罚/.test(JSON.stringify(g))) fail("L-PRO-08 missing discipline news");

// Mira intimate
const miraFold = foldText(N["A1-TOWN-04"]);
if (!/跨坐/.test(miraFold)) fail("A1-TOWN-04 fold missing 跨坐");

// Companion desire topic
const dalt = JSON.stringify(N["D-ALT"]);
if (!/s2_desire/.test(dalt)) fail("D-ALT missing s2_desire companion intimacy choice");
if (!/"t":"fold"/.test(dalt)) fail("D-ALT missing fold");

// Edric first-meet fold
const tavernFolds = allBlocks(N["A1-TOWN-02"]).filter((b) => b.t === "fold");
if (!tavernFolds.some((b) => b.cond && b.cond.pc === "edric")) fail("A1-TOWN-02 missing edric-cond fold");

// Coy leftovers still banned
for (const bad of ["守门兵随后擅离岗位找你，引发纪律处罚和一条后续新闻。", "只耗一段短文本。"]) {
  for (const [nid, n] of Object.entries(N)) {
    if (JSON.stringify(n).includes(bad)) fail(`coy leftover in ${nid}: ${bad}`);
  }
}

if (failed) { console.error("TOTAL FAIL", failed); process.exit(1); }
console.log("PASS foldout checklist;", NEED_FOLD.length, "nodes checked");
