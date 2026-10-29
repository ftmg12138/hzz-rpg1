#!/usr/bin/env node
/** Phase 1: equip power, fall threshold, container beat, dossiers meta */
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

// --- combat power / equip ---
{
  const s = E.newState("liriel");
  E.ensureBags(s);
  const before = E.combatPower(s);
  assert(before >= 3, "liriel base power should include rapier+chain+dex (>=3), got " + before);
  const unequip = E.unequipSlot(s, "weapon");
  assert(unequip.ok, "unequip weapon");
  const mid = E.combatPower(s);
  assert(mid === before - 2, `unequip rapier should -2 power (${before} -> ${mid})`);
  const eq = E.equipItem(s, "elf_rapier");
  assert(eq.ok, "re-equip");
  assert(E.combatPower(s) === before, "re-equip restores power");
  // combat advantage flag path
  const ck = { combat: true, stats: ["DEX"], dc: 99 };
  // simulate choose internals: adv when power>=4
  assert(E.combatPower(s) >= 3, "power present");
  // give chalk unequipped; equip shadow if available — boost with old_hammer not in bag
  // force high power
  s.items.push("old_hammer");
  E.equipItem(s, "old_hammer");
  assert(E.combatPower(s) >= 4, "power >=4 after hammer, got " + E.combatPower(s));
  console.log("equip/power OK", E.equipSummary(s));
}

// --- fall threshold ---
{
  const s = E.newState("liriel");
  const toasts = [];
  E.apply(s, [{ op: "add", k: "fall", v: 3 }], toasts);
  assert(E.num(s, "fall") === 3, "fall 3");
  assert(!s.vars.fall_threshold_4, "no threshold yet");
  E.apply(s, [{ op: "add", k: "fall", v: 1 }], toasts);
  assert(E.num(s, "fall") === 4, "fall 4");
  assert(s.vars.fall_threshold_4 === true, "threshold flag");
  assert(toasts.some((t) => /沉沦已达阈值|饲养/.test(t.text)), "threshold toast: " + JSON.stringify(toasts));
  console.log("fall threshold OK", toasts.map((t) => t.text));
}

// --- container beat depth ---
{
  const c = (function find(chs, id) {
    for (const x of chs || []) {
      if (x.id === id) return x;
      const r = find(x.sub, id);
      if (r) return r;
    }
  })(nodes["A1-TOWN-02"].choices, "t4_li_show");
  assert(c, "t4_li_show exists");
  assert(c.result.length >= 3, "expanded result blocks");
  assert(c.result.some((b) => b.t === "fold"), "has fold");
  assert(c.effects.some((e) => e.k === "shared_fragment_truth"), "shared truth");
  console.log("container beat OK", c.result.length, "blocks");
}

// --- dossiers + stats help ---
{
  assert(meta.dossiers && meta.dossiers.liriel && meta.dossiers.liriel.appear, "liriel dossier");
  assert(meta.stats_help && meta.stats_help.power && meta.stats_help.fall, "stats_help");
  const s = E.newState("liriel");
  s.vars.met_valen = true;
  s.vars.dossier_valen_depth = 1;
  console.log("dossier meta OK");
}

// --- stash_slot ---
{
  const s = E.newState("edric");
  s.node = "A1-STASH-01";
  const beforeItems = s.items.slice();
  const toasts = [];
  const weapon = s.equip.weapon;
  E.apply(s, [{ op: "stash_slot", v: "weapon" }], toasts);
  assert(s.storage.includes(weapon), "weapon in storage");
  assert(!s.items.includes(weapon), "weapon left bag");
  assert(s.equip.weapon == null, "unequipped on stash");
  console.log("stash_slot OK", toasts.map((t) => t.text));
}

// --- fall>=4 tavern choice exists ---
{
  const c = nodes["A1-TOWN-02"].choices.find((x) => x.id === "fall4_patron_hint");
  assert(c && c.cond, "fall4 patron choice");
  console.log("fall4 tavern choice OK");
}

console.log("ALL PHASE1 UNIT TESTS PASSED");
