// Execute every choice and nested sub-choice with both high and low rolls.
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..", "public");
global.window = undefined;
eval(fs.readFileSync(path.join(root, "js/checks.js"), "utf8"));
eval(fs.readFileSync(path.join(root, "js/engine.js"), "utf8"));

const nodes = JSON.parse(fs.readFileSync(path.join(root, "data/nodes.json"), "utf8"));
const meta = JSON.parse(fs.readFileSync(path.join(root, "data/meta.json"), "utf8"));
const E = globalThis.WZCEngine;
E.init(nodes, meta);

const requiredAssets = [
  ...["edric", "liriel", "thorin"].map((id) => path.join(root, "assets", "characters", `${id}.jpg`)),
  ...Object.values(nodes)
    .filter((node) => node.kind === "ending")
    .map((node) => path.join(root, "assets", "endings", `${node.id}.jpg`)),
];

function setCmp(state, [key, op, value], wanted) {
  const delta = typeof value === "number" ? 1 : 0;
  let actual = value;
  if (wanted) {
    if (op === ">") actual = value + delta;
    if (op === "<") actual = value - delta;
    if (op === "!=") actual = typeof value === "number" ? value + 1 : `not-${value}`;
  } else {
    if ([">=", ">", "==", "="].includes(op)) actual = typeof value === "number" ? value - 1 : `not-${value}`;
    if (["<=", "<"].includes(op)) actual = typeof value === "number" ? value + 1 : `not-${value}`;
    if (op === "!=") actual = value;
  }
  if (key === "hp") state.hp = actual;
  else state.vars[key] = actual;
}

function satisfy(state, cond, wanted = true) {
  if (!cond || cond.else) return;
  if (cond.not) return satisfy(state, cond.not, !wanted);
  if (cond.all) {
    if (wanted) cond.all.forEach((part) => satisfy(state, part, true));
    else if (cond.all.length) satisfy(state, cond.all[0], false);
    return;
  }
  if (cond.any) {
    if (wanted && cond.any.length) satisfy(state, cond.any[0], true);
    else cond.any.forEach((part) => satisfy(state, part, false));
    return;
  }
  if (cond.pc) state.pc = wanted ? cond.pc : ["edric", "liriel", "thorin"].find((pc) => pc !== cond.pc);
  if (cond.eq) state.vars[cond.eq[0]] = wanted ? cond.eq[1] : "__different__";
  if (cond.flag) {
    state.vars[cond.flag] = wanted;
    if (!wanted) state.items = state.items.filter((item) => item !== cond.flag);
  }
  if (cond.seen) state.seen[cond.seen] = wanted;
  if (cond.ending) state.vars.ending = wanted ? cond.ending : "__different__";
  if (cond.cmp) setCmp(state, cond.cmp, wanted);
}

function fresh(nodeId, pathChoices) {
  const pcCond = pathChoices.map((choice) => choice.cond && choice.cond.pc).find(Boolean);
  const state = E.newState(pcCond || "edric");
  state.node = nodeId;
  state.seen[nodeId] = true;
  state.vars.vouchers = 999;
  state.vars.curse_stage = 0;
  state.hp = 99;
  state.max_hp = 99;
  state.stats = { STR: 10, DEX: 10, CON: 10, CHA: 10, INS: 10, WIL: 10 };
  pathChoices.forEach((choice) => satisfy(state, choice.cond, true));
  return state;
}

const paths = [];
function collect(nodeId, list, parents = []) {
  for (const choice of list || []) {
    const current = parents.concat(choice);
    paths.push({ nodeId, choices: current });
    collect(nodeId, choice.sub, current);
  }
}
for (const [nodeId, node] of Object.entries(nodes)) collect(nodeId, node.choices);

const errors = [];
const warnings = [];
for (const asset of requiredAssets) {
  if (!fs.existsSync(asset) || fs.statSync(asset).size < 1024) errors.push(`missing or empty art asset: ${path.relative(root, asset)}`);
}
const originalWarn = console.warn;
console.warn = (...args) => warnings.push(args.join(" "));

let runs = 0;
for (const entry of paths) {
  for (const highRoll of [false, true]) {
    const state = fresh(entry.nodeId, entry.choices);
    E.setRng(() => (highRoll ? 0.999999 : 0));
    try {
      let output = E.choose(state, entry.choices[0], null);
      for (let index = 1; index < entry.choices.length; index += 1) {
        const pending = E.resolvePending(state);
        if (!pending) throw new Error(`missing pending parent before ${entry.choices[index].id}`);
        const choice = entry.choices[index];
        satisfy(state, choice.cond, true);
        if (!E.visibleSubs(state, entry.nodeId, pending.parent).some((candidate) => candidate.id === choice.id)) {
          throw new Error(`condition could not expose nested choice ${choice.id}`);
        }
        output = E.chooseSub(state, choice);
      }
      if (!output) throw new Error("engine returned no result");
      if (state.node !== "__TITLE__" && !nodes[state.node]) throw new Error(`landed on missing node ${state.node}`);
      if (state.vars.vouchers < 0) throw new Error(`currency fell below zero (${state.vars.vouchers})`);
      runs += 1;
    } catch (error) {
      const ids = entry.choices.map((choice) => choice.id).join(">");
      errors.push(`${entry.nodeId}/${ids} ${highRoll ? "high" : "low"}: ${error.message}`);
    }
  }
}

console.warn = originalWarn;
if (warnings.length) errors.push(...warnings.map((warning) => `console warning: ${warning}`));

if (errors.length) {
  console.error(`all-choice test: ${errors.length} failure(s) after ${runs} successful runs`);
  errors.slice(0, 30).forEach((error) => console.error(`  - ${error}`));
  process.exit(1);
}

console.log(`all-choice test: OK (${paths.length} choice paths, ${runs} high/low executions)`);
