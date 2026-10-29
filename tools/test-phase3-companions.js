#!/usr/bin/env node
/** Verify party selection, mine losses, shrine absence, and city storage. */
const fs = require("fs");
const path = require("path");
const root = path.join(__dirname, "..", "public");
eval(fs.readFileSync(path.join(root, "js/checks.js"), "utf8"));
eval(fs.readFileSync(path.join(root, "js/engine.js"), "utf8"));
const nodes = JSON.parse(fs.readFileSync(path.join(root, "data/nodes.json"), "utf8"));
const meta = JSON.parse(fs.readFileSync(path.join(root, "data/meta.json"), "utf8"));
const E = globalThis.WZCEngine;
E.init(nodes, meta);
const assert = (value, message) => { if (!value) throw new Error(message); };
const find = (node, id) => nodes[node].choices.find((choice) => choice.id === id);
const ids = (state, node) => E.visibleChoices(state, node).map((choice) => choice.id);

for (const [pc, peer] of [["edric", "liriel"], ["liriel", "thorin"], ["thorin", "edric"]]) {
  const state = E.newState(pc);
  state.vars[`met_${peer}`] = true;
  state.vars.companion = peer;
  E.enter(state, "A2-MINE-00", { blocks: [], toasts: [] });
  assert(state.vars.companion === null, "warehouse companion followed to mine without consent");
  assert(!ids(state, state.node).includes("a"), "mine route bypasses party choice");
  assert(ids(state, state.node).includes(`party_${peer}`), `cannot recruit ${peer}`);
  E.choose(state, find(state.node, `party_${peer}`));
  assert(state.vars.companion === peer, `recruitment did not name ${peer}`);
  assert(!ids(state, state.node).includes("party_solo"), "party can be overwritten after commitment");
  assert(ids(state, state.node).includes("a"), "party commitment did not unlock mine routes");
  state.node = "A2-MINE-10";
  E.choose(state, find(state.node, "s1c2"));
  assert(state.node === "A2-MINE-10B", "collapse skipped the rescue decision");
  assert(ids(state, state.node).includes(`rescue_${peer}`), `${peer} rescue hidden`);
  E.choose(state, find(state.node, `abandon_${peer}`));
  assert(state.vars[`alt_${peer}_dead`], `${peer} death was not recorded`);
  assert(state.vars.companion === null, "dead companion is still selected");
  assert(state.node === "A2-MINE-11", "mine exit failed");
  assert(E.blocksFor(state, "A3-SHRINE-01").some((block) => block.text && block.text.includes(`${{ edric: "艾德里克", liriel: "莉瑞尔", thorin: "索林" }[peer]}死在黑砧`)), "shrine does not acknowledge death");
  assert(!ids(state, "A3-SHRINE-03~2").includes({ edric: "s3c6", liriel: "s3c7", thorin: "s3c8" }[peer]), "dead companion can swear an oath");
}

{
  const state = E.newState("edric");
  state.node = "A1-TOWN-08";
  const prep = find(state.node, "prep_comp");
  assert(!E.visibleSubs(state, state.node, prep).some((choice) => choice.id === "comp_li"), "unknown Liriel can be summoned to warehouse");
  state.vars.met_liriel = true;
  assert(E.visibleSubs(state, state.node, prep).some((choice) => choice.id === "comp_li"), "known Liriel cannot be summoned");
}

{
  const state = E.newState("liriel");
  const edricQuiet = find("D-ALT", "t1").sub.find((choice) => choice.id === "s1c4");
  E.apply(state, edricQuiet.effects, []);
  assert(state.items.includes("lily_comb") && state.vars.peer_supported_edric, "Edric's comb was only granted in prose");
  const thorPress = find("D-ALT", "t3").sub.find((choice) => choice.id === "s3c2");
  E.apply(state, thorPress.effects, []);
  assert(state.vars.fall_thorin === 1, "pressuring Thorin has no personal fall cost");
  state.vars.companion = "thorin";
  state.node = "A2-MINE-09";
  E.choose(state, find(state.node, "witness_delegate_thorin"));
  assert(state.vars.fall_thorin === 3 && state.vars.truth === 1, "delegated witness cost did not apply");
  state.vars.fall_thorin = 4;
  state.node = "A2-MINE-10B";
  const hpBefore = state.hp;
  E.choose(state, find(state.node, "rescue_thorin"));
  assert(state.hp === hpBefore - 3, "deeply fallen companion's rescue cost was not applied");
  assert(state.vars.fall_thorin === 3, "rescue did not reduce companion fall");
}

{
  const state = E.newState("edric");
  state.vars.met_liriel = true;
  state.node = "CITY-HUB";
  assert(ids(state, state.node).includes("peer_city_liriel"), "city peer scene hidden");
  E.choose(state, find(state.node, "peer_city_liriel"));
  assert(state.node === "CITY-PEER-LIRIEL", "city peer scene did not open");
  E.choose(state, find(state.node, "liriel_boundary"));
  assert(state.vars.liriel_stopword_shared, "boundary choice has no payoff");
  state.node = "CITY-SAFE-01";
  assert(E.canUseStorage(state), "city safe point does not enable storage");
  const weapon = state.equip.weapon;
  assert(E.stashItem(state, weapon).ok, "city safe point could not store equipment");
  assert(E.takeStash(state, weapon).ok, "city safe point could not retrieve equipment");
}

{
  const state = E.newState("liriel");
  state.node = "CITY-SAFE-01";
  assert(E.storageCapacity(state) === 6, "base storage capacity changed");
  state.storage = Array.from({ length: 6 }, (_, index) => `stored_${index}`);
  assert(!E.stashItem(state, state.items[0]).ok, "full storage accepted an item");
  state.items.push("free_storage_token");
  assert(E.storageCapacity(state) === 7, "free storage reward has no effect");
  assert(E.stashItem(state, state.items[0]).ok, "extra storage slot is unusable");
  state.items.push("merchant_storage_token");
  assert(E.storageCapacity(state) === 10, "merchant storage reward has no effect");
  while (state.items.length <= 8) state.items.push(`carried_${state.items.length}`);
  const burdenedPower = E.combatPower(state);
  state.items.push("sewn_pack_strap");
  assert(E.carryCapacity(state) === 10, "pack strap has no effect");
  assert(E.combatPower(state) === burdenedPower + 2, "pack strap did not remove overload penalty");
}

{
  const state = E.newState("edric");
  state.vars.met_liriel = true;
  state.vars.four_bones_present = true;
  state.node = "A3-SHRINE-07";
  const plan = find(state.node, "p1");
  assert(plan.sub.some((choice) => choice.id === "p1c_liriel"), "named inner-ring volunteer missing");
  assert(!plan.sub.some((choice) => choice.id === "p1c"), "unnamed inner-ring volunteer remains");
  E.apply(state, plan.sub.find((choice) => choice.id === "p1c_liriel").effects, []);
  const end = E.blocksFor(state, "END-02").map((block) => block.text || "").join("\n");
  assert(end.includes("莉瑞尔独自站在内环"), "volunteer ending omits named companion");
  assert(!end.includes("冲击把你掀进内环"), "volunteer ending claims player took the cost");
  assert(!end.includes("照心骨没有到场"), "four-bone ending claims the fourth bone is absent");
}

{
  const state = E.newState("thorin");
  state.node = "A3-SHRINE-07";
  const forced = find(state.node, "p5").sub.find((choice) => choice.id === "p5b");
  E.apply(state, forced.effects, []);
  const end = E.blocksFor(state, "END-10").map((block) => block.text || "").join("\n");
  assert(end.includes("毫不知情的人"), "forced guardian cost not shown");
  assert(!end.includes("四个人从雾钟城四座门离开"), "forced route repeats voluntary guardian ending");
}

console.log("phase3 companions: OK");
