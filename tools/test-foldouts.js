#!/usr/bin/env node
/** Foldout explicit-prose checklist: surface stays tame; fold blocks hold explicit beats.
 *  Also writes tools/liriel-fold-coverage.json — full inventory of liriel/intimacy candidates.
 */
const fs = require("fs");
const path = require("path");
const N = JSON.parse(fs.readFileSync(path.join(__dirname, "../public/data/nodes.json"), "utf8"));

const KEY_LIRIEL = /莉瑞尔|liriel|银链|苔冠|魅惑/;
const KEY_INTIM = /交合|情欲描写|情欲|乳尖|跨坐|高潮|鸡巴|肉棒|湿穴|穴口|湿透|吞吐|射精|精液|操进|吃进|插入|裤裆|床笫|做爱|性爱|情事|赤裸|勃起|欲火|解开衣|湿热|腿间/;

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
  return allBlocks(n)
    .filter((b) => b.t === "fold")
    .map((b) => JSON.stringify(b.blocks || b.text || ""))
    .join("\n");
}
function blobOf(n) {
  return JSON.stringify(n);
}

let failed = 0;
function fail(msg) {
  console.error("FAIL:", msg);
  failed++;
}

// ---- Required folds (must exist)
const NEED_FOLD = [
  // prologue / desire pool / mira / companion (prior pass)
  "L-PRO-02", "L-PRO-06", "L-PRO-07", "L-PRO-08",
  "R-DES-01", "R-DES-03", "R-DES-04", "R-DES-05", "R-DES-06",
  "A1-TOWN-04", "D-ALT", "A1-TOWN-02",
  // this audit pass
  "D-NPC-MIRA", "C-03", "A2-MINE-07", "A2-MINE-09", "A3-SHRINE-06", "END-01",
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

// Mira intimate (town)
const miraFold = foldText(N["A1-TOWN-04"]);
if (!/跨坐/.test(miraFold)) fail("A1-TOWN-04 fold missing 跨坐");

// Companion desire topic
const dalt = JSON.stringify(N["D-ALT"]);
if (!/s2_desire/.test(dalt)) fail("D-ALT missing s2_desire companion intimacy choice");
if (!/"t":"fold"/.test(dalt)) fail("D-ALT missing fold");
// charm guard surface must not say 交合
if (/用被点着的交合换过路/.test(surfaceText(N["D-ALT"]))) fail("D-ALT charm surface still says 交合");
if (!/交合|鸡巴|骑上去/.test(foldText(N["D-ALT"]))) fail("D-ALT charm fold missing explicit beat");

// Edric + Thorin first-meet folds
const tavernFolds = allBlocks(N["A1-TOWN-02"]).filter((b) => b.t === "fold");
if (!tavernFolds.some((b) => b.cond && b.cond.pc === "edric")) fail("A1-TOWN-02 missing edric-cond fold");
if (!tavernFolds.some((b) => b.cond && b.cond.pc === "thorin")) fail("A1-TOWN-02 missing thorin-cond fold");

// Late shrine hunger-bone
if (!/饥月|交合|腿根/.test(foldText(N["A3-SHRINE-06"]))) fail("A3-SHRINE-06 fold missing desire surge");

// Coy leftovers still banned
for (const bad of ["守门兵随后擅离岗位找你，引发纪律处罚和一条后续新闻。", "只耗一段短文本。", "用被点着的交合换过路"]) {
  for (const [nid, n] of Object.entries(N)) {
    if (surfaceText(n).includes(bad) || (bad === "只耗一段短文本。" && blobOf(n).includes(bad))) {
      // for 交合 phrase, only fail if on surface
      if (bad === "用被点着的交合换过路") {
        if (surfaceText(n).includes(bad)) fail(`coy leftover on surface in ${nid}: ${bad}`);
      } else if (blobOf(n).includes(bad)) {
        fail(`coy leftover in ${nid}: ${bad}`);
      }
    }
  }
}

// ---- Full inventory → coverage JSON
const inventory = [];
for (const [id, n] of Object.entries(N)) {
  const blob = blobOf(n);
  const surf = surfaceText(n);
  const folds = allBlocks(n).filter((b) => b.t === "fold");
  const lirielish = KEY_LIRIEL.test(blob) || /^L-PRO|^R-DES|^D-ALT|^D-NPC-MIRA/.test(id);
  const intimacy = KEY_INTIM.test(blob);
  if (!lirielish && !intimacy) continue;
  let cls = "d";
  if (folds.length) {
    if (KEY_INTIM.test(surf) && /交合|乳尖|跨坐|高潮|鸡巴|肉棒|操进|吃进|射精|裤裆|欲火|解开衣带|腿间/.test(surf)) cls = "b";
    else cls = "a";
  } else if (intimacy) {
    cls = "c";
  } else {
    cls = "d";
  }
  inventory.push({
    id,
    title: n.title || "",
    cls,
    folds: folds.length,
    required: NEED_FOLD.includes(id),
    lirielish,
    intimacy,
  });
}
const by = { a: [], b: [], c: [], d: [] };
for (const row of inventory) by[row.cls].push(row.id);

const coverage = {
  generated: new Date().toISOString(),
  scanned: inventory.length,
  counts: { a_has_fold: by.a.length, b_surface_explicit: by.b.length, c_intimacy_no_fold: by.c.length, d_no_intimacy: by.d.length },
  required_folds: NEED_FOLD,
  classified: by,
  inventory,
  notes: [
    "a = already has fold and surface is PG enough",
    "b = has fold but surface still carries explicit lexemes (should move into fold)",
    "c = intimacy markers without fold (gap)",
    "d = liriel/银链/苔冠/魅惑 mention with no intimacy staging",
    "Mid/late scripts (A2/A3/END) mostly lack dedicated sex scenes; R-DES pool fires across the run for liriel PC.",
  ],
};
fs.writeFileSync(path.join(__dirname, "liriel-fold-coverage.json"), JSON.stringify(coverage, null, 2), "utf8");

if (by.b.length) {
  console.warn("WARN surface-explicit (b):", by.b.join(", "));
}
if (by.c.length) {
  // Only fail if a required node is in c; otherwise warn — thematic 欲望 mentions may false-positive
  for (const id of by.c) {
    if (NEED_FOLD.includes(id)) fail(`${id} classified c but is required to have fold`);
  }
  console.warn("WARN intimacy-no-fold (c) non-required:", by.c.join(", "));
}

if (failed) {
  console.error("TOTAL FAIL", failed);
  process.exit(1);
}
console.log(
  "PASS foldout checklist;",
  NEED_FOLD.length,
  "required;",
  "scanned",
  inventory.length,
  "a/b/c/d",
  by.a.length,
  by.b.length,
  by.c.length,
  by.d.length
);
