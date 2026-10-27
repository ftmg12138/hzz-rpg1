/** Skill checks: d20 + floor((stat-10)/2) + mods >= DC */
(function (global) {
  function mod(stat) {
    return Math.floor((Number(stat) - 10) / 2);
  }

  function rollD20() {
    return 1 + Math.floor(Math.random() * 20);
  }

  /**
   * @param {object} state game state
   * @param {object} check {stats, dc, advantage, disadvantage, alt_dc, mods}
   * @returns {{ok:boolean, total:number, roll:number, rolls:number[], dc:number, stat:string, modifier:number, natural:number, text:string}}
   */
  function performCheck(state, check) {
    if (!check) return { ok: true, total: 20, roll: 20, rolls: [20], dc: 0, stat: "", modifier: 0, natural: 20, text: "" };
    const stats = check.stats && check.stats.length ? check.stats : ["INS"];
    // Pick best available stat for "A 或 B"
    let best = stats[0];
    let bestMod = -99;
    for (const s of stats) {
      const m = mod(state.stats[s] ?? 10);
      if (m > bestMod) {
        bestMod = m;
        best = s;
      }
    }
    let dc = check.dc || 13;
    if (check.alt_dc && check.alt_dc.when) {
      const flag = String(check.alt_dc.when).replace(/[`\s]/g, "");
      // loose: if any matching flag is truthy
      const keys = Object.keys(state.flags || {});
      const hit = keys.some((k) => flag.includes(k) && state.flags[k]) || state.flags[flag];
      if (hit) dc = check.alt_dc.dc;
    }
    let situational = 0;
    // wounded disadvantage already handled via flag
    if (state.flags && state.flags.memory_anchor_honest && (best === "WIL" || best === "INS")) {
      // one free success consumed by engine if desired — here just +2 flavor
    }
    const rolls = [];
    let roll;
    if (check.advantage && !check.disadvantage) {
      const a = rollD20(), b = rollD20();
      rolls.push(a, b);
      roll = Math.max(a, b);
    } else if (check.disadvantage && !check.advantage) {
      const a = rollD20(), b = rollD20();
      rolls.push(a, b);
      roll = Math.min(a, b);
    } else {
      roll = rollD20();
      rolls.push(roll);
    }
    // wounded: first physical check at disadvantage already baked if check.disadvantage set by engine
    const total = roll + bestMod + situational;
    const ok = total >= dc;
    const natural = roll;
    const text = `检定 ${stats.join("/")}：d20=${rolls.join("/")} ${bestMod >= 0 ? "+" : ""}${bestMod} = ${total}（DC ${dc}）→ ${ok ? "成功" : "失败"}`;
    return { ok, total, roll, rolls, dc, stat: best, modifier: bestMod, natural, text };
  }

  global.WZCChecks = { mod, rollD20, performCheck };
})(typeof window !== "undefined" ? window : globalThis);
