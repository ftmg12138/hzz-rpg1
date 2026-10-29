#!/usr/bin/env node
/** Checklist: Liriel desire/charm nodes must not keep the coy summary blurbs. */
const fs = require("fs");
const path = require("path");
const N = JSON.parse(fs.readFileSync(path.join(__dirname, "../public/data/nodes.json"), "utf8"));

const MUST_NOT = [
  "守门兵随后擅离岗位找你，引发纪律处罚和一条后续新闻。",
  "被你引开的男人会在镇里执着寻找你。",
  "只耗一段短文本。",
  "且腐化。",
  "合理边界。",
  "短战斗，残酷。",
];

const MUST_HAVE = {
  "L-PRO-08": ["乳尖", "纪律处罚", "擅离"],
  "L-PRO-07": ["交合", "高潮"],
  "L-PRO-06": ["银链", "寻找"],
  "R-DES-03": ["门板"],
  "R-DES-06": ["欲火"],
  "A1-TOWN-04": ["跨坐", "高潮"],
};

let failed = 0;
for (const [nid, n] of Object.entries(N)) {
  const blob = JSON.stringify(n);
  for (const bad of MUST_NOT) {
    if (blob.includes(bad)) {
      console.error("COY leftover in", nid, ":", bad);
      failed++;
    }
  }
}
for (const [nid, needles] of Object.entries(MUST_HAVE)) {
  const blob = JSON.stringify(N[nid] || {});
  for (const needle of needles) {
    if (!blob.includes(needle)) {
      console.error("Missing explicit prose in", nid, ":", needle);
      failed++;
    }
  }
}

// Inventory nodes reviewed this pass
const REVIEWED = [
  "L-PRO-02", "L-PRO-06", "L-PRO-07", "L-PRO-08",
  "A1-TOWN-04", "D-NPC-MIRA", "D-ALT",
  "R-DES-01", "R-DES-02", "R-DES-03", "R-DES-04", "R-DES-05", "R-DES-06",
];
console.log("Reviewed:", REVIEWED.join(", "));
if (failed) {
  console.error("FAIL", failed);
  process.exit(1);
}
console.log("PASS liriel desire explicitness checklist");
