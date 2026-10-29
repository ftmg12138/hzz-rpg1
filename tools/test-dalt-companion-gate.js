// PC must not see themselves as companion in D-ALT.
const fs = require("fs");
const path = require("path");
const root = path.join(__dirname, "..", "public");
eval(fs.readFileSync(path.join(root, "js/checks.js"), "utf8"));
eval(fs.readFileSync(path.join(root, "js/engine.js"), "utf8"));
const nodes = JSON.parse(fs.readFileSync(path.join(root, "data/nodes.json"), "utf8"));
const meta = JSON.parse(fs.readFileSync(path.join(root, "data/meta.json"), "utf8"));
const E = globalThis.WZCEngine;
E.init(nodes, meta);

const map = { edric: "与艾德里克深入交谈。", liriel: "与莉瑞尔深入交谈。", thorin: "与索林深入交谈。" };
let fail = 0;
for (const pc of Object.keys(map)) {
  const s = E.newState(pc);
  s.node = "D-ALT";
  for (const other of Object.keys(map)) if (other !== pc) s.vars[`met_${other}`] = true;
  const labels = E.visibleChoices(s, "D-ALT").map((c) => c.label);
  if (labels.includes(map[pc])) {
    console.error(`FAIL: ${pc} still sees ${map[pc]}`, labels);
    fail++;
  } else {
    console.log(`OK: ${pc} hidden self; visible=`, labels.filter((l) => /深入交谈/.test(l)));
  }
  for (const [other, lab] of Object.entries(map)) {
    if (other === pc) continue;
    if (!labels.includes(lab)) {
      console.error(`FAIL: ${pc} missing companion ${lab}`, labels);
      fail++;
    }
  }
}
// Mira intimacy topic only for liriel
for (const pc of ["edric", "liriel", "thorin"]) {
  const s = E.newState(pc);
  s.node = "A1-TOWN-04";
  const labels = E.visibleChoices(s, "A1-TOWN-04").map((c) => c.label);
  const has = labels.some((l) => l.includes("情欲躁动") || l.includes("银链带来"));
  if (pc === "liriel" && !has) { console.error("FAIL: liriel missing mira desire topic", labels); fail++; }
  if (pc !== "liriel" && has) { console.error("FAIL: non-liriel sees mira desire", pc, labels); fail++; }
}
if (fail) process.exit(1);
console.log("dalt companion gate + mira desire OK");
