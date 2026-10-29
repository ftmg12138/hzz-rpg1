#!/usr/bin/env node
/**
 * Build public/data/gate.json (hashes only) from private-delivery/source-packs.json.
 * Plaintext packs are never embedded in this file.
 */
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const SRC = path.join(ROOT, "private-delivery/source-packs.json");
const PUBLIC = path.join(ROOT, "public/data/gate.json");
const PRIVATE = path.join(ROOT, "private-delivery/rpg-gate-credentials-10.txt");
const WORKSPACE_COPY = "/workspace/rpg-gate-credentials-10.txt";

function sha256(s) {
  return crypto.createHash("sha256").update(s, "utf8").digest("hex");
}

if (!fs.existsSync(SRC)) {
  console.error("Missing", SRC, "— create private source packs first (gitignored).");
  process.exit(1);
}

const PACKS = JSON.parse(fs.readFileSync(SRC, "utf8"));

function patternGrid(p) {
  const set = new Set(p.split(""));
  const order = {};
  p.split("").forEach((d, i) => { order[d] = i + 1; });
  return ["123", "456", "789"]
    .map((row) =>
      row.split("").map((d) => (set.has(d) ? `[${order[d]}]` : " · ")).join("")
    )
    .join("\n");
}

const seenPass = new Set();
const seenPat = new Set();
for (const p of PACKS) {
  if (p.pattern.length < 4) throw new Error(`pattern too short: ${p.id}`);
  if (!/^[1-9]+$/.test(p.pattern)) throw new Error(`bad pattern: ${p.id}`);
  if (new Set(p.pattern).size !== p.pattern.length) throw new Error(`dup dots: ${p.id}`);
  if (seenPass.has(p.password)) throw new Error(`dup password: ${p.id}`);
  if (seenPat.has(p.pattern)) throw new Error(`dup pattern: ${p.id}`);
  seenPass.add(p.password);
  seenPat.add(p.pattern);
}

const accounts = PACKS.map((p) => ({
  id: p.id,
  pass: sha256(p.password),
  gate: sha256(`${p.password}|${p.pattern}`),
}));

fs.writeFileSync(
  PUBLIC,
  JSON.stringify(
    {
      version: 1,
      algo: "SHA-256",
      scheme: "pass = sha256(password); gate = sha256(password + '|' + patternDigits)",
      pattern: "dots 1-9 left-to-right top-to-bottom; min 4 unique dots",
      accounts,
    },
    null,
    2
  ) + "\n"
);

const lines = [];
lines.push("雾钟城：第七声 — 封面门禁凭证包（10 组）");
lines.push("生成时间（Asia/Hong_Kong）：" + new Date().toLocaleString("zh-CN", { timeZone: "Asia/Hong_Kong" }));
lines.push("站点：https://rpg.xyzhzz.com");
lines.push("");
lines.push("用法：打开封面 → 输入「口令」→ 点「验证口令」→ 在 3×3 九点阵上画出「手势」→ 解锁进入标题页。");
lines.push("会话：解锁状态保存在 sessionStorage（同标签页刷新仍解锁；关闭标签后再开需重新登录）。");
lines.push("点位编号（左→右，上→下）：");
lines.push("  1 2 3");
lines.push("  4 5 6");
lines.push("  7 8 9");
lines.push("");
lines.push("⚠️ 本文件含明文口令与手势，请勿提交到公开仓库或部署到 Pages。");
lines.push("⚠️ 若旧版生成器曾入库，本组口令已轮换，请只用本文件。");
lines.push("=".repeat(56));
lines.push("");

for (const p of PACKS) {
  lines.push(`【组 ${p.id}】`);
  lines.push(`口令：${p.password}`);
  lines.push(`手势（数字串）：${p.pattern}`);
  lines.push(`手势说明：${p.note || ""}`);
  lines.push("矩阵（[序号] 为经过顺序，· 为未经过）：");
  lines.push(patternGrid(p.pattern));
  lines.push("-".repeat(40));
  lines.push("");
}

const body = lines.join("\n");
fs.writeFileSync(PRIVATE, body, "utf8");
fs.writeFileSync(WORKSPACE_COPY, body, "utf8");
console.log("Wrote", PUBLIC);
console.log("Wrote", PRIVATE);
console.log("Wrote", WORKSPACE_COPY);
