#!/usr/bin/env node
/** Playable-state regressions for the tavern, warehouse, oath, and companion arcs. */
const fs = require("fs");
const path = require("path");
const root = path.join(__dirname, "..", "public");
eval(fs.readFileSync(path.join(root, "js/checks.js"), "utf8"));
eval(fs.readFileSync(path.join(root, "js/engine.js"), "utf8"));
const nodes = JSON.parse(fs.readFileSync(path.join(root, "data/nodes.json"), "utf8"));
const meta = JSON.parse(fs.readFileSync(path.join(root, "data/meta.json"), "utf8"));
const E = globalThis.WZCEngine;
E.init(nodes, meta);
const assert = (condition, message) => { if (!condition) throw new Error(message); };
const ids = (choices) => choices.map((choice) => choice.id);

{
  const all = ids(nodes["A1-TOWN-02"].choices);
  assert(all.length === new Set(all).size, "the tavern repeats a choice ID");
  const s = E.newState("liriel");
  assert(ids(E.visibleChoices(s, "A1-TOWN-02")).includes("t4_li"), "Liriel cannot meet Edric");
  assert(!ids(E.visibleChoices(s, "A1-TOWN-02")).includes("talk_D-ALT"), "unknown companions can be addressed");
  s.vars.met_edric = true;
  assert(ids(E.visibleChoices(s, "D-ALT")).includes("t1"), "known Edric cannot be addressed");
  assert(!ids(E.visibleChoices(s, "D-ALT")).includes("t3"), "unknown Thorin can be addressed");
  s.vars.alt_edric_dead = true;
  assert(!ids(E.visibleChoices(s, "D-ALT")).includes("t1"), "dead Edric can be addressed");
  s.vars.talked_ysolde = true;
  assert(!ids(E.visibleChoices(s, "D-NPC-YSOLDE")).includes("t1"), "Ysolde repeats her first greeting");
}

{
  const s = E.newState("liriel");
  s.node = "A3-SHRINE-03~2";
  s.vars.alt_edric_dead = true;
  s.vars.alt_thorin_dead = true;
  const visible = ids(E.visibleChoices(s, s.node));
  assert(visible.includes("s3c7"), "Liriel cannot make her own oath");
  assert(!visible.includes("s3c6") && !visible.includes("s3c8"), "absent holders can make an oath");
}

{
  const s = E.newState("edric");
  const weapon = s.equip.weapon;
  assert(!E.stashItem(s, weapon).ok, "storage works outside a safe point");
  s.node = "A1-STASH-01";
  const before = E.combatPower(s);
  assert(E.stashItem(s, weapon).ok, "weapon was not stored");
  assert(s.storage.includes(weapon) && !s.items.includes(weapon), "stored item remains carried");
  assert(E.combatPower(s) < before, "storage did not lower power");
  assert(s.vars.warehouse_stashed === 1 && s.vars.warehouse_enemy_advantage, "warehouse delay not tracked");
  const next = s.items.find((id) => id !== meta.characters[s.pc].fragment);
  assert(E.stashItem(s, next).ok, "second slot did not work");
  const third = s.items.find((id) => id !== meta.characters[s.pc].fragment);
  assert(!E.stashItem(s, third).ok, "warehouse accepted a third item");
  E.setRng((() => { let i = 0; return () => [0.9, 0.1][i++ % 2]; })());
  s.node = "C-04";
  const out = E.choose(s, nodes["C-04"].choices.find((c) => c.id === "a"));
  assert(out.check && out.check.dis && out.check.rolls.length === 2, "enemy advantage did not affect the opening roll");
}

{
  const s = E.newState("liriel");
  const drink = nodes["D-ALT"].choices.find((c) => c.id === "t1").sub.find((c) => c.id === "s1_drink");
  E.apply(s, drink.effects, []);
  assert(s.vars.fall_edric === 1 && s.vars.fall === 0, "Edric's drinking increased Liriel's fall");
  E.apply(s, [{ op: "add", k: "fall", v: 1 }], []);
  assert(s.vars.fall_liriel === 1, "player fall and personal fall diverged");
  const payment = nodes["CITY-05"].choices.find((c) => c.id === "city05_desire").sub.find((c) => c.id === "c05_use");
  assert(payment.cost && payment.cost.vouchers === 1, "Sarei's quoted fee has no cost");
}

console.log("revision regressions: OK");
