#!/usr/bin/env node
/** Phase 2: fall endings reachable, Act2/3 folds, Liriel desire choices, 第七声 beats */
const fs = require("fs");
const path = require("path");
const root = path.join(__dirname, "..", "public");
eval(fs.readFileSync(path.join(root, "js/checks.js"), "utf8"));
eval(fs.readFileSync(path.join(root, "js/engine.js"), "utf8"));
const nodes = JSON.parse(fs.readFileSync(path.join(root, "data/nodes.json"), "utf8"));
const meta = JSON.parse(fs.readFileSync(path.join(root, "data/meta.json"), "utf8"));
const E = globalThis.WZCEngine;
E.init(nodes, meta);

function assert(cond, msg) { if (!cond) { console.error("FAIL:", msg); process.exit(1); } }
function findChoice(chs, id) {
  for (const x of chs || []) {
    if (x.id === id) return x;
    const r = findChoice(x.sub, id);
    if (r) return r;
  }
  return null;
}
function countFolds(n) {
  let nF = 0;
  function walk(bs) {
    for (const b of bs || []) {
      if (b && b.t === "fold") nF++;
      walk(b.blocks);
    }
  }
  walk(n.blocks);
  const stack = [...(n.choices || [])];
  while (stack.length) {
    const c = stack.pop();
    walk(c.result);
    stack.push(...(c.sub || []));
  }
  return nF;
}

assert(/^2\.[23]\.\d/.test(meta.version), "version " + meta.version);
assert(meta.phase2 && meta.phase2.fall_endings.length === 3, "phase2 meta");

for (const id of ["END-FALL-LIRIEL", "END-FALL-EDRIC", "END-FALL-THORIN"]) {
  assert(nodes[id] && nodes[id].kind === "ending", id + " ending node");
  assert(fs.existsSync(path.join(root, "assets/endings", id + ".jpg")), id + " art");
  assert(fs.statSync(path.join(root, "assets/endings", id + ".jpg")).size > 250000, id + " art size");
  const pc = id.split("-").at(-1).toLowerCase();
  assert((meta.epilogues[pc] || []).some((e) => /沉沦/.test(e.label || "") && e.text), id + " epilogue text");
}

// fall>=6 toast + hub choice visible
{
  for (const pc of ["liriel", "edric", "thorin"]) {
    const s = E.newState(pc);
    const toasts = [];
    E.apply(s, [{ op: "add", k: "fall", v: 6 }], toasts);
    assert(s.vars.fall_threshold_6 === true, pc + " fall6 flag");
    assert(toasts.some((t) => /沉沦已达极限|沉沦极限/.test(t.text)), pc + " fall6 toast");
    s.node = "CITY-HUB";
    const vis = E.visibleChoices(s, "CITY-HUB");
    assert(vis.some((c) => c.id === "fall6_collapse"), pc + " hub fall6 choice visible");
    // enter fall ending via sub
    const parent = findChoice(nodes["CITY-HUB"].choices, "fall6_collapse");
    const subId = pc === "liriel" ? "fall6_l" : pc === "edric" ? "fall6_e" : "fall6_t";
    const sub = findChoice(parent.sub, subId);
    assert(sub && sub.next.startsWith("END-FALL"), pc + " sub next");
    E.apply(s, sub.effects, []);
    const out = { toasts: [], blocks: [] };
    E.enter(s, sub.next, out);
    assert(s.node === sub.next, pc + " entered " + s.node);
    assert(nodes[s.node].kind === "ending", pc + " kind ending");
    const epi = E.epilogue(s);
    assert(epi && /沉沦/.test(epi.label || ""), pc + " fall epilogue: " + JSON.stringify(epi));
    console.log("fall ending OK", pc, s.node, epi.label);
  }
}

// shrine p_fall
{
  const s = E.newState("liriel");
  E.apply(s, [{ op: "add", k: "fall", v: 6 }], []);
  s.node = "A3-SHRINE-07";
  const vis = E.visibleChoices(s, "A3-SHRINE-07");
  assert(vis.some((c) => c.id === "p_fall"), "shrine p_fall visible");
}

// Liriel desire choices present
for (const [nid, cid] of [
  ["A2-MINE-09", "mine09_desire_submit"],
  ["CITY-03", "city03_desire"],
  ["CITY-05", "city05_desire"],
  ["CITY-08", "city08_desire"],
  ["SQ-CITY-02", "sq02_patron"],
  ["A3-SHRINE-01", "shrine01_desire"],
  ["A3-SHRINE-03~2", "oath_liriel_hunger"],
]) {
  assert(findChoice(nodes[nid].choices, cid), nid + " " + cid);
}

// 第七声 beats
for (const [nid, fid] of [
  ["CITY-08", "seventh_city08"],
  ["A3-SHRINE-04", "seventh_shrine04"],
  ["A3-SHRINE-07", "seventh_shrine07"],
  ["A2-MINE-08", "seventh_mine08"],
]) {
  assert((nodes[nid].blocks || []).some((b) => b.id === fid), fid);
}

// fold density floors
let act2 = 0, act3 = 0, city = 0;
for (const [nid, n] of Object.entries(nodes)) {
  const f = countFolds(n);
  if (nid.startsWith("A2-") || nid.includes("MINE")) act2 += f;
  else if (nid.startsWith("A3-") || nid.includes("SHRINE")) act3 += f;
  else if (nid.startsWith("CITY") || nid.startsWith("SQ-CITY")) city += f;
}
assert(act2 >= 10, "act2 folds >=10 got " + act2);
assert(act3 >= 8, "act3 folds >=8 got " + act3);
assert(city >= 15, "city folds >=15 got " + city);
console.log("fold coverage OK", { act2, act3, city });

// Phase1 still intact
{
  const s = E.newState("liriel");
  E.ensureBags(s);
  assert(E.combatPower(s) >= 3, "phase1 power intact");
  assert(meta.stats_help && meta.stats_help.power, "stats_help intact");
  assert(findChoice(nodes["A1-TOWN-02"].choices, "t4_li_show"), "container beat intact");
}

console.log("phase2 ALL OK");
