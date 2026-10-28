// node tools/test-epro05-settlement.js
// Regression: Mara escort settlement at E-PRO-05 must grant guild vouchers.
const fs = require("fs"), path = require("path");
const root = path.join(__dirname, "..", "public");
eval(fs.readFileSync(path.join(root, "js/checks.js"), "utf8"));
eval(fs.readFileSync(path.join(root, "js/engine.js"), "utf8"));
const nodes = JSON.parse(fs.readFileSync(path.join(root, "data/nodes.json"), "utf8"));
const meta = JSON.parse(fs.readFileSync(path.join(root, "data/meta.json"), "utf8"));
const E = globalThis.WZCEngine;
E.init(nodes, meta);

function enterWith(flags) {
  const s = E.newState("edric");
  const startV = s.vars.vouchers;
  Object.assign(s.vars, flags);
  // Force first-enter so enter_effects fire
  delete s.seen["E-PRO-05"];
  const out = { blocks: [], toasts: [] };
  E.enter(s, "E-PRO-05", out);
  return { s, gained: s.vars.vouchers - startV, toasts: out.toasts, startV };
}

const cases = [
  { name: "saved Peter, no extras", flags: { saved_peter: true }, expect: 28 },
  { name: "saved Peter + coffer", flags: { saved_peter: true, coffer_saved: true }, expect: 32 },
  { name: "saved Peter + bonus", flags: { saved_peter: true, promised_bonus: true }, expect: 30 },
  { name: "saved Peter + coffer + bonus", flags: { saved_peter: true, coffer_saved: true, promised_bonus: true }, expect: 34 },
  { name: "peter injured (goods kept)", flags: { peter_injured: true }, expect: 32 },
  { name: "peter injured + bonus", flags: { peter_injured: true, promised_bonus: true }, expect: 34 },
  { name: "fallback (no flags)", flags: {}, expect: 28 },
];

let fail = 0;
for (const c of cases) {
  const { gained, toasts } = enterWith(c.flags);
  const toastHit = toasts.some((t) => /商会券/.test(t.text || ""));
  const ok = gained === c.expect && toastHit;
  console.log(`${ok ? "OK" : "FAIL"} ${c.name}: gained=${gained} expect=${c.expect} toast=${toastHit}`);
  if (!ok) fail++;
}

// Medical fee choice: deduct 6 via cost after settlement
{
  const { s, gained } = enterWith({ peter_injured: true });
  const choice = nodes["E-PRO-05"].choices.find((c) => (c.label || "").includes("医药费"));
  if (!choice) { console.log("FAIL missing medical fee choice"); fail++; }
  else {
    const before = s.vars.vouchers;
    E.choose(s, choice, null);
    const after = s.vars.vouchers;
    const ok = before - after === 6 && s.vars.sacrifice >= 1;
    console.log(`${ok ? "OK" : "FAIL"} medical fee: ${before}->${after} sacrifice=${s.vars.sacrifice}`);
    if (!ok) fail++;
  }
}

// Built data must contain voucher enter_effects
{
  const ee = nodes["E-PRO-05"].enter_effects || [];
  const ok = ee.some((e) => {
    const ops = e.ops || e.effects || [e];
    return ops.some((o) => o.op === "add" && o.k === "vouchers" && o.v > 0);
  });
  console.log(`${ok ? "OK" : "FAIL"} nodes.json E-PRO-05 enter_effects grant vouchers (${ee.length} entries)`);
  if (!ok) fail++;
}

if (fail) { console.error(`\n${fail} failure(s)`); process.exit(1); }
console.log("\nall settlement tests passed");
