/** 雾钟城 v2 引擎：纯状态机，不碰 DOM。 */
(function (global) {
  const C = () => global.WZCChecks;
  let NODES = {}, META = {};
  let rng = Math.random;

  const REL_NAMES = {
    kael: "凯尔", mira: "米拉", harlan: "哈兰", helga: "赫尔嘉", eilyn: "艾琳", miners: "矿工们",
    tom: "小汤姆", mara: "玛拉", toren: "托伦", valen: "瓦伦", ysolde: "伊索尔", gromm: "格罗姆",
    lily: "莉莉", shadow: "灰袍人", bran: "布兰",
  };
  const VAR_TOASTS = {
    resonance: ["钟声在骨头里更响了", null],
    corruption: ["残片的低语离你更近了", "你推开了残片的低语"],
    curse_stage: ["回声病又加重了一层", "回声病稍稍退去"],
    truth: ["你离长誓钟的真相更近了一步", null],
    sanctuary_clues: ["你又找到一条通往初鸣庭的线索", null],
    alarm_town: ["镇上的警戒更严了", "镇上的警戒松了些"],
    alarm_mine: ["矿区的警戒更严了", "矿区的警戒松了些"],
    city_rep: ["城里有人开始记住你的好", "城里的流言对你不利"],
  };

  function init(nodes, meta) { NODES = nodes; META = meta; }
  function setRng(f) { rng = f; C().setRng(f); }

  function newState(pcId) {
    const ch = META.characters[pcId];
    const vars = { time: 0, resonance: 0, truth: 0, alarm_town: 0, alarm_mine: 0, city_actions: 0, city_rep: 0,
      curse_stage: 1, sanctuary_clues: 0, mercy: 0, cruelty: 0, sacrifice: 0, corruption: 0, defiance: 0, vouchers: 0 };
    const items = [];
    for (const it of ch.carried || []) {
      const m = /^(\d+)_vouchers$/.exec(it);
      if (m) vars.vouchers += Number(m[1]); else items.push(it);
    }
    if (ch.fragment) items.push(ch.fragment);
    vars.private_goal = ch.private_goal;
    return {
      v: 2, pc: pcId, name: ch.name, stats: Object.assign({}, ch.stats), hp: ch.hp, max_hp: ch.max_hp || ch.hp,
      vars, items, node: ch.start, stack: [], used: {}, seen: {}, travel: 0, adv: {}, dis: {},
      journal: [`以${ch.name}的身份踏入雨夜。`], curse_done: [], extra_used: {}, ended: null,
    };
  }

  // ---------- 条件 ----------
  function num(s, k) {
    if (k.startsWith("mod.")) return Math.floor(((s.stats && s.stats[k.slice(4)]) || 10) / 2) - 5;
    const v = s.vars[k]; return typeof v === "number" ? v : v ? 1 : 0; }
  function test(s, c) {
    if (!c) return true;
    if (c.else) return true;
    if (c.pc) return s.pc === c.pc;
    if (c.flag) return !!s.vars[c.flag] || s.items.includes(c.flag);
    if (c.seen) return !!s.seen[c.seen];
    if (c.ending) return s.vars.ending === c.ending;
    if (c.all) return c.all.every((x) => test(s, x));
    if (c.any) return c.any.some((x) => test(s, x));
    if (c.not) return !test(s, c.not);
    if (c.cmp) {
      const [k, op, v] = c.cmp;
      const a = k === "hp" ? s.hp : num(s, k);
      switch (op) {
        case ">=": return a >= v; case "<=": return a <= v; case ">": return a > v;
        case "<": return a < v; case "==": case "=": return a == v; case "!=": return a != v;
      }
    }
    return true;
  }

  // ---------- 效果 ----------
  function itemName(k) { return (META.item_names || {})[k] || null; }
  function apply(s, effects, toasts) {
    for (const e of effects || []) {
      // Grouped conditional batch: {cond, ops:[...]} (same shape as choice.cond_effects)
      if (e.ops || e.effects) {
        if (e.cond && !test(s, e.cond)) continue;
        apply(s, e.ops || e.effects, toasts);
        continue;
      }
      if (e.cond && !test(s, e.cond)) continue;
      const k = e.k;
      switch (e.op) {
        case "add": {
          const before = num(s, k);
          s.vars[k] = before + Number(e.v || 0);
          toastVar(k, Number(e.v || 0), toasts);
          break;
        }
        case "set": s.vars[k] = e.v; break;
        case "max": s.vars[k] = Math.max(num(s, k), Number(e.v)); break;
        case "push": (s.vars[k] = Array.isArray(s.vars[k]) ? s.vars[k] : []).push(e.v); break;
        case "hp": {
          const d = Number(e.v || 0);
          s.hp = Math.max(0, Math.min(s.max_hp, s.hp + d));
          toasts.push(d < 0 ? { t: "bad", text: `你受了伤（体力 ${d}）` } : { t: "good", text: `伤势好转（体力 +${d}）` });
          break;
        }
        case "item": {
          if (e.v === false) {
            s.items = s.items.filter((x) => x !== k);
            s.vars[k] = false;
            const n = itemName(k);
            if (n) toasts.push({ t: "bad", text: `失去：「${n}」` });
          }
          else if (!s.items.includes(k)) {
            s.items.push(k); s.vars[k] = true;
            const n = itemName(k); if (n) toasts.push({ t: "good", text: `获得：「${n}」` });
          }
          break;
        }
        case "adv": s.adv[k || "*"] = true; toasts.push({ t: "good", text: "你为下一次尝试占得了先机" }); break;
        case "dis": s.dis[k || "*"] = true; toasts.push({ t: "bad", text: "下一次尝试会更难" }); break;
      }
    }
  }
  function toastVar(k, d, toasts) {
    if (!d) return;
    if (k === "vouchers") { toasts.push({ t: d > 0 ? "good" : "bad", text: d > 0 ? `收下 ${d} 张商会券` : `付出 ${-d} 张商会券` }); return; }
    if (k.startsWith("rel.")) {
      const n = REL_NAMES[k.slice(4)];
      if (n) toasts.push({ t: d > 0 ? "good" : "bad", text: d > 0 ? `${n}对你多了几分信任` : `${n}对你冷淡了些` });
      return;
    }
    const m = VAR_TOASTS[k];
    if (m) { const txt = d > 0 ? m[0] : m[1]; if (txt) toasts.push({ t: d > 0 && k !== "city_rep" && k !== "truth" && k !== "sanctuary_clues" ? "bad" : "good", text: txt }); }
  }

  // ---------- 可见选项 ----------
  function key(nodeId, c, parent) { return nodeId + "/" + (parent ? parent.id + ">" : "") + c.id; }
  function hub(s, n) {
    if (!n.hub) return null;
    const h = n.hub, count = num(s, h.counter);
    const limit = h.count_up ? null : (h.limit || 0) + (s.extra_used[n.id] ? 1 : 0);
    return { h, count, limit, left: limit == null ? null : Math.max(0, limit - count), full: limit != null && count >= limit };
  }
  function visibleChoices(s, nodeId) {
    const n = NODES[nodeId];
    if (!n) return [];
    const hb = hub(s, n);
    if (hb && hb.full) {
      const out = [{ id: "__advance", label: hb.h.advance.label, next: hb.h.advance.next, result: [{ t: "p", text: hb.h.advance.text }], effects: [], synthetic: true }];
      if (hb.h.extra && !s.extra_used[nodeId]) out.push({ id: "__extra", label: hb.h.extra.label, result: [{ t: "p", text: hb.h.extra.text }], effects: hb.h.extra.effects, next: "__SELF__", synthetic: true, extra: true });
      return out;
    }
    const out = n.choices.filter((c) => {
      if (c.once && s.used[key(nodeId, c)]) return false;
      if (c.cond && !test(s, c.cond)) return false;
      return true;
    });
    if (!out.length && n.default_next) out.push({ id: "__cont", label: "继续。", next: n.default_next, result: [], effects: [], synthetic: true });
    if (!out.length && s.stack.length) out.push({ id: "__ret", label: "继续。", next: "__RETURN__", result: [], effects: [], synthetic: true });
    return out;
  }
  function visibleSubs(s, nodeId, parent) {
    return (parent.sub || []).filter((c) => !(c.cond && !test(s, c.cond)) && !(c.once && s.used[key(nodeId, c, parent)]));
  }
  function canAfford(s, c) { return !(c.cost && c.cost.vouchers && num(s, "vouchers") < c.cost.vouchers); }
  function displayLabel(s, c) {
    let l = c.label;
    if (c.mark && test(s, c.mark.cond)) l += `（${c.mark.suffix}）`;
    return l;
  }

  // ---------- 进入节点 ----------
  function failNodeFor(id) {
    for (const r of META.fail_rules || []) if (r.prefix.some((p) => id.startsWith(p))) return r.node;
    return "FAIL-05";
  }
  function enter(s, target, out) {
    let guard = 0;
    while (guard++ < 20) {
      if (target === "__RETURN__") { target = s.stack.pop() || s.node; continue; }
      if (target === "__ENDING__") { target = s.vars.ending || "END-05"; continue; }
      if (target === "__SELF__") target = s.node;
      break;
    }
    if (target === "__TITLE__") { s.node = "__TITLE__"; return; }
    if (!NODES[target]) { console.warn("missing node", target); target = failNodeFor(s.node); }
    const wf = META.wound_fail;
    if (wf && wf.endings.includes(target) && s.hp <= wf.hp_max) target = wf.node;
    const first = !s.seen[target];
    s.node = target; s.seen[target] = true;
    const n = NODES[target];
    if (first && n.enter_effects) apply(s, n.enter_effects, out.toasts);
    if (n.kind === "ending") {
      s.ended = target;
      if (!s.journal.includes("结局：" + n.title)) s.journal.push("结局：" + n.title);
    } else if (first && n.kind !== "dialogue" && !target.startsWith("R-")) {
      s.journal.push(n.title);
    }
    // 雾钟城的诅咒节拍
    if (n.hub && n.hub.curse_checks) {
      const cnt = num(s, n.hub.counter);
      for (const step of n.hub.curse_checks) {
        if (cnt >= step && !s.curse_done.includes(step)) {
          s.curse_done.push(step);
          s.vars.curse_stage = num(s, "curse_stage") + 1;
          out.blocks.push({ t: "note", text: "你在街角停下来咳嗽。掌心里的血带着铁锈和钟油的味道——回声病又往前走了一步。" });
          out.toasts.push({ t: "bad", text: "回声病又加重了一层" });
        }
      }
      const cf = META.curse_fail;
      if (cf && num(s, "curse_stage") >= cf.stage) return enter(s, cf.node, out);
      if (cf && num(s, "curse_stage") === cf.stage - 1 && !s.vars.curse_warned) {
        s.vars.curse_warned = true;
        out.blocks.push({ t: "note", text: "你扶着墙站了很久才缓过来。身体在告诉你：再发作一次，你就撑不住了。是时候去找治疗的办法，或者尽快离开这座城。" });
        out.toasts.push({ t: "bad", text: "回声病已濒临极限" });
      }
    }
  }

  // ---------- 主动作 ----------
  /**
   * 选择一个选项。返回 {label, check, blocks, toasts, subs, pendingTarget}
   * 若有子选项，状态停留在当前节点，前端显示子选项；否则已跳转。
   */
  function choose(s, choice, parent) {
    const nodeId = s.node, n = NODES[nodeId];
    s.pending = null;
    const out = { label: displayLabel(s, choice), blocks: [], toasts: [], check: null, checkText: "", subs: null, parent: null };
    if (!canAfford(s, choice)) { out.blocks.push({ t: "note", text: "你手头的商会券不够。" }); return out; }
    if (choice.cost && choice.cost.vouchers) { s.vars.vouchers -= choice.cost.vouchers; toastVar("vouchers", -choice.cost.vouchers, out.toasts); }
    if (choice.once || choice.hub_visit || choice.talk || choice.topic) s.used[key(nodeId, choice, parent)] = true;
    if (choice.extra) s.extra_used[nodeId] = true;
    if (choice.hub_count && n.hub) s.vars[n.hub.counter] = num(s, n.hub.counter) + 1;
    apply(s, choice.effects, out.toasts);
    for (const ce of choice.cond_effects || []) if (test(s, ce.cond)) apply(s, ce.ops || ce.effects, out.toasts);
    out.blocks.push(...(choice.result || []).filter((b) => !b.cond || test(s, b.cond)));
    let branch = null;
    if (choice.check) {
      const ck = choice.check;
      const stats = ck.stats || [];
      const adv = (ck.adv_if && test(s, ck.adv_if)) || s.adv["*"] || stats.some((x) => s.adv[x]);
      const dis = s.dis["*"] || stats.some((x) => s.dis[x]);
      s.adv = {}; s.dis = {};
      const auto = ck.auto_if && test(s, ck.auto_if);
      const info = C().roll(s.stats, ck, { adv, dis, auto });
      out.check = info; out.checkText = C().describe(info, ck);
      if (auto && ck.auto_text) out.blocks.push({ t: "note", text: ck.auto_text });
      branch = info.ok ? choice.success : choice.fail;
      if (branch) { apply(s, branch.effects, out.toasts); out.blocks.push(...(branch.result || []).filter((b) => !b.cond || test(s, b.cond))); }
    }
    const subs = visibleSubs(s, nodeId, choice);
    if (subs.length) {
      out.subs = subs; out.parent = choice;
      out.branchNext = (branch && branch.next) || (parent && parent._branchNext) || null;
      s.pending = { path: ((parent && parent._path) || []).concat(choice.id), bn: out.branchNext,
        view: { label: out.label, blocks: out.blocks, checkText: out.checkText, ok: out.check ? out.check.ok : null } };
      return finishCheckHP(s, out);
    }
    let target = (branch && branch.next) || choice.next;
    if (!target || target === "__SELF__") {
      if (parent) target = parent.topic ? "__SELF__" : (parent._branchNext || (parent.next && parent.next !== "__SELF__" ? parent.next : null)) || (n.stay_choices ? "__SELF__" : n.default_next) || "__SELF__";
      else target = target || n.default_next || "__SELF__";
    }
    const call = (branch && branch.call) || choice.call || (parent && !parent.topic && !parent._called && parent.call) || null;
    // 战斗/插曲中途被带离（被俘、入狱、夺舍）时，丢弃原本要返回的位置
    if (choice.unwind || (branch && branch === choice.fail && choice.unwind_fail)) s.stack.pop();
    if (call) {
      s.stack.push(target === "__SELF__" ? nodeId : target);
      target = call;
    } else if (choice.travel && target !== "__SELF__") {
      s.travel += 1;
      const r = META.random || {};
      const hit = s.travel >= (r.guarantee || 3) || rng() < (r.chance || 0.35);
      if (hit) {
        const pool = Object.keys(NODES).filter((id) => id.startsWith("R-") && !s.seen[id] && (NODES[id].pools || []).some((p) => p === "travel" || p === s.pc));
        if (pool.length) { s.travel = 0; s.stack.push(target); target = pool[Math.floor(rng() * pool.length)]; }
      }
    }
    if (target === n.default_next && n.routes) for (const r of n.routes) if (test(s, r.cond)) { target = r.next; break; }
    if (s.hp <= 0) target = failNodeFor(nodeId);
    out.target = target;
    enter(s, target, out);
    return out;
  }
  function finishCheckHP(s, out) {
    if (s.hp <= 0) { const t = failNodeFor(s.node); out.subs = null; out.target = t; enter(s, t, out); }
    return out;
  }
  function resolvePending(s) {
    if (!s.pending || !NODES[s.node]) return null;
    let list = NODES[s.node].choices, c = null;
    for (const id of s.pending.path) { c = (list || []).find((x) => x.id === id); if (!c) return null; list = c.sub; }
    const parent = Object.assign({}, c, { _branchNext: s.pending.bn, _path: s.pending.path });
    return { parent, subs: visibleSubs(s, s.node, c, s.pending.path), view: s.pending.view };
  }
  function chooseSub(s, sub) {
    const r = resolvePending(s);
    if (!r) return null;
    return choose(s, sub, r.parent);
  }

  // ---------- 渲染辅助 ----------
  function blocksFor(s, nodeId) { return (NODES[nodeId].blocks || []).filter((b) => !b.cond || test(s, b.cond)); }
  function epilogue(s) {
    const list = (META.epilogues || {})[s.pc] || [];
    return list.find((v) => v.cond && !v.cond.else && test(s, v.cond)) || list.find((v) => v.cond && v.cond.else) || null;
  }
  function timeLabel(s) { const t = META.time_labels || []; return t[Math.min(num(s, "time"), t.length - 1)] || ""; }

  global.WZCEngine = { init, setRng, newState, test, apply, visibleChoices, visibleSubs, resolvePending, canAfford, displayLabel, choose, chooseSub, enter, hub, blocksFor, epilogue, timeLabel, num, REL_NAMES };
})(typeof window !== "undefined" ? window : globalThis);
