// 无头随机模拟：node tools/sim.js [runs]
const fs = require("fs"), path = require("path");
const root = path.join(__dirname, "..", "public");
global.window = undefined;
eval(fs.readFileSync(path.join(root, "js/checks.js"), "utf8"));
eval(fs.readFileSync(path.join(root, "js/engine.js"), "utf8"));
const nodes = JSON.parse(fs.readFileSync(path.join(root, "data/nodes.json")));
const meta = JSON.parse(fs.readFileSync(path.join(root, "data/meta.json")));
const E = globalThis.WZCEngine; E.init(nodes, meta);
let seed = 1; const rnd = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
E.setRng(rnd);
const runs = Number(process.argv[2] || 3000);
const failFrom = {}, endings = {}, visited = new Set(), stuck = {}, errors = [], lengths = [];
for (let r = 0; r < runs; r++) {
  const pc = ["edric", "liriel", "thorin"][r % 3];
  const s = E.newState(pc); s.seen[s.node] = true; visited.add(s.node);
  let steps = 0;
  try {
    while (steps++ < 1500) {
      if (s.node === "__TITLE__") break;
      const n = nodes[s.node];
      if (n.kind === "ending") { endings[s.node] = (endings[s.node] || 0) + 1; break; }
      const pend = E.resolvePending(s);
      const list = pend ? pend.subs : E.visibleChoices(s, s.node).filter((c) => E.canAfford(s, c));
      if (!list.length) { stuck[s.node + (pend ? "(sub)" : "")] = (stuck[s.node] || 0) + 1; break; }
      const c = list[Math.floor(rnd() * list.length)];
      const before = s.node;
      if (pend) E.chooseSub(s, c); else E.choose(s, c, null);
      if (s.node.startsWith("FAIL-")) { const k = s.node + "<" + before; failFrom[k] = (failFrom[k] || 0) + 1; }
      visited.add(s.node);
    }
    if (steps >= 1500) stuck["LOOP@" + s.node] = (stuck["LOOP@" + s.node] || 0) + 1;
    lengths.push(steps);
  } catch (e) { errors.push(`${pc} @${s.node}: ${e.stack.split("\n").slice(0, 3).join(" | ")}`); }
}
const all = Object.keys(nodes);
console.log("runs", runs, "avg steps", Math.round(lengths.reduce((a, b) => a + b, 0) / lengths.length));
console.log("endings", Object.keys(endings).length, JSON.stringify(endings));
console.log("stuck", JSON.stringify(stuck));
console.log("errors", errors.length, errors.slice(0, 5));
console.log("never visited", all.filter((x) => !visited.has(x)).join(" "));
console.log("fail from", JSON.stringify(Object.entries(failFrom).sort((a,b)=>b[1]-a[1]).slice(0,15)));
