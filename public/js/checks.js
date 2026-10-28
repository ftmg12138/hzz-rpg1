/** 检定：d20 + floor((属性-10)/2) ≥ DC */
(function (global) {
  const STAT_NAMES = { STR: "力量", DEX: "敏捷", CON: "体魄", CHA: "魅力", INS: "洞察", WIL: "意志" };
  const DC_WORDS = { 10: "较易", 13: "中等", 16: "困难", 19: "极难" };
  let rng = Math.random;

  function mod(stat) { return Math.floor((Number(stat || 10) - 10) / 2); }
  function d20() { return 1 + Math.floor(rng() * 20); }
  function dcWord(dc) {
    if (DC_WORDS[dc]) return DC_WORDS[dc];
    if (dc <= 10) return "较易";
    if (dc <= 13) return "中等";
    if (dc <= 16) return "困难";
    return "极难";
  }
  function statLabel(stats) { return (stats || []).map((s) => STAT_NAMES[s] || s).join("或"); }
  function tag(check) {
    if (!check) return "";
    return `${statLabel(check.stats)} · ${dcWord(check.dc)}`;
  }

  /** opts: {adv, dis, auto} */
  function roll(stats, check, opts) {
    opts = opts || {};
    const list = check.stats && check.stats.length ? check.stats : ["INS"];
    let best = list[0], bestMod = -99;
    for (const s of list) { const m = mod(stats[s]); if (m > bestMod) { bestMod = m; best = s; } }
    const dc = check.dc || 13;
    if (opts.auto) return { ok: true, auto: true, dc, stat: best, modifier: bestMod, rolls: [], total: 0 };
    const rolls = [d20()];
    let r = rolls[0];
    const adv = opts.adv && !opts.dis, dis = opts.dis && !opts.adv;
    if (adv || dis) { rolls.push(d20()); r = adv ? Math.max(...rolls) : Math.min(...rolls); }
    const total = r + bestMod;
    return { ok: total >= dc, dc, stat: best, modifier: bestMod, rolls, natural: r, total, adv, dis };
  }

  function describe(info, check) {
    const t = tag(check);
    if (info.auto) return `「${t}」自然成功`;
    const m = info.modifier >= 0 ? `+${info.modifier}` : `${info.modifier}`;
    const dice = info.rolls.length > 1 ? `${info.rolls.join("、")}取${info.adv ? "高" : "低"}` : `${info.natural}`;
    return `「${t}」${info.ok ? "成功" : "失败"}　掷出 ${dice}，${STAT_NAMES[info.stat]} ${m}，合计 ${info.total}`;
  }

  global.WZCChecks = { STAT_NAMES, mod, d20, dcWord, statLabel, tag, roll, describe, setRng: (f) => { rng = f; } };
})(typeof window !== "undefined" ? window : globalThis);
