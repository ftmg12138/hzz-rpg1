(function (global) {
  const TIME_LABELS = ["黄昏", "入夜", "深夜", "午夜", "三更", "四更", "黎明"];

  function createInitialState(charDef) {
    const flags = {
      tom_alive: true,
      alt_a_alive: true,
      alt_b_alive: true,
    };
    // mark fragment item
    const carried = (charDef.carried || []).slice();
    if (charDef.fragment && !carried.includes(charDef.fragment)) carried.push(charDef.fragment);

    return {
      protagonist: charDef.id,
      characterName: charDef.name,
      stats: Object.assign({}, charDef.stats),
      hp: charDef.hp,
      max_hp: charDef.max_hp,
      carried,
      storage: (charDef.storage || []).slice(),
      vouchers: extractVouchers(carried),
      fragment: charDef.fragment,
      private_goal: charDef.private_goal,
      private_goal_state: "unresolved",
      time: 0,
      resonance: 0,
      truth: 0,
      alarm_town: 0,
      alarm_mine: 0,
      city_actions: 0,
      city_rep: 0,
      curse_stage: 1,
      sanctuary_clues: 0,
      fragment_pressure: 1,
      fragment_used: 0,
      fragment_resisted: 0,
      mercy: 0,
      cruelty: 0,
      sacrifice: 0,
      corruption: 0,
      defiance: 0,
      town_visits: 0,
      rel: {
        valen: 0, eilyn: 0, gromm: 0, kael: 0, harlan: 0, mira: 0,
        skye: 0, toren: 0, ysolde: 0, helga: 0, tom: 0, mara: 0,
        alt_a: 0, alt_b: 0,
      },
      flags,
      journal: [],
      visited: [],
      nodeId: charDef.start,
      returnStack: [],
      lastCheck: null,
      endingsSeen: [],
      rng_seed: Date.now() % 1e9,
    };
  }

  function extractVouchers(items) {
    let n = 0;
    for (const it of items) {
      const m = String(it).match(/^(\d+)_vouchers$/);
      if (m) n += Number(m[1]);
    }
    return n;
  }

  function get(state, key) {
    if (key.startsWith("rel.")) return state.rel[key.slice(4)] ?? 0;
    if (key in state) return state[key];
    if (state.flags && key in state.flags) return state.flags[key];
    return undefined;
  }

  function set(state, key, value) {
    if (key.startsWith("rel.")) {
      const k = key.slice(4);
      state.rel[k] = clamp(Number(value), -3, 3);
      return;
    }
    const known = [
      "time", "resonance", "truth", "alarm_town", "alarm_mine", "city_actions",
      "city_rep", "curse_stage", "sanctuary_clues", "fragment_pressure",
      "fragment_used", "fragment_resisted", "mercy", "cruelty", "sacrifice",
      "corruption", "defiance", "hp", "max_hp", "vouchers", "town_visits",
      "private_goal", "private_goal_state",
    ];
    if (known.includes(key)) {
      state[key] = value;
      if (key === "hp") state.hp = Math.max(0, Math.min(state.max_hp, Number(value)));
      if (key === "time") state.time = clamp(Number(value), 0, 6);
      if (key === "resonance") state.resonance = clamp(Number(value), 0, 6);
      return;
    }
    state.flags[key] = value;
  }

  function clamp(n, a, b) {
    return Math.max(a, Math.min(b, n));
  }

  function applyEffects(state, effects) {
    if (!effects || !effects.length) return [];
    const notes = [];
    for (const e of effects) {
      if (!e || !e.op) continue;
      if (e.op === "ending") {
        notes.push({ type: "ending", id: e.key });
        continue;
      }
      if (e.op === "add_item") {
        if (!state.carried.includes(e.key)) state.carried.push(e.key);
        notes.push({ type: "item", key: e.key });
        continue;
      }
      if (e.op === "=") {
        set(state, e.key, e.value);
        notes.push({ type: "set", key: e.key, value: e.value });
      } else if (e.op === "+=") {
        const cur = Number(get(state, e.key) ?? 0);
        set(state, e.key, cur + Number(e.value));
        notes.push({ type: "add", key: e.key, value: e.value });
      } else if (e.op === "-=") {
        const cur = Number(get(state, e.key) ?? 0);
        set(state, e.key, cur - Number(e.value));
        notes.push({ type: "add", key: e.key, value: -Number(e.value) });
      }
    }
    // wound flags
    const ratio = state.hp / state.max_hp;
    state.flags.wounded = ratio < 0.5 && state.hp > 0;
    state.flags.critical = ratio < 0.25 && state.hp > 0;
    return notes;
  }

  function evalCondition(state, cond) {
    if (!cond) return true;
    const raw = (cond.raw || "").trim();
    if (!raw) return true;
    // flags in backticks
    if (cond.flags && cond.flags.length) {
      return cond.flags.every((f) => {
        // expressions like ambush_read
        if (f.includes(" ")) return looseTruth(state, f);
        const v = get(state, f);
        return Boolean(v);
      });
    }
    return looseTruth(state, raw);
  }

  function looseTruth(state, raw) {
    const s = raw.replace(/`/g, "");
    // OR
    if (s.includes("或")) {
      return s.split("或").some((p) => looseTruth(state, p.trim()));
    }
    // DEX 修正至少 +2
    const m = s.match(/(STR|DEX|CON|CHA|INS|WIL)\s*修正至少\s*\+?(\d+)/);
    if (m) {
      return WZCChecks.mod(state.stats[m[1]]) >= Number(m[2]);
    }
    // 汤姆同行 / 汤姆可行动
    if (/汤姆/.test(s)) {
      return Boolean(state.flags.tom_companion || state.flags.tom_alive);
    }
    // 见过灰袍人
    if (/灰袍/.test(s)) return Boolean(state.flags.shadow_seen || state.flags.shadow_named_hint);
    // bare flag name
    const bare = s.match(/^[a-zA-Z_][\w.]*$/);
    if (bare) return Boolean(get(state, bare[0]));
    // if contains a known flag token
    for (const k of Object.keys(state.flags)) {
      if (state.flags[k] && s.includes(k)) return true;
    }
    // default: show the option (lenient) unless it clearly requires a false flag
    if (/^未|没有|不/.test(s)) return true;
    return true; // lenient visibility
  }

  function woundLevel(state) {
    const r = state.hp / state.max_hp;
    if (state.hp <= 0) return "濒死";
    if (r < 0.25) return "重伤";
    if (r < 0.5) return "负伤";
    if (r < 0.85) return "轻伤";
    return "安好";
  }

  function resonanceLabel(n) {
    return ["沉寂", "微颤", "低鸣", "回荡", "轰鸣", "裂响", "崩溃"][clamp(n, 0, 6)];
  }

  function filterChoices(state, node) {
    return (node.choices || []).filter((c) => evalCondition(state, c.condition));
  }

  function goto(state, nodeId, nodes) {
    if (nodeId === "__TITLE__") return { type: "title" };
    if (nodeId === "__RETURN__") {
      const back = state.returnStack.pop() || state.nodeId;
      state.nodeId = back;
      return { type: "node", id: back };
    }
    if (!nodes[nodeId]) {
      state.journal.push("失落的路径：" + nodeId);
      state.nodeId = "__STUB__";
      return { type: "node", id: "__STUB__" };
    }
    state.nodeId = nodeId;
    if (!state.visited.includes(nodeId)) state.visited.push(nodeId);
    // Soft timers for hubs
    if (nodeId === "A1-TOWN-01" && state.town_visits >= 2 && state.time < 3) {
      // after second deep visit suggest clock — handled by patches linking A1-TOWN-08
    }
    if (state.town_visits >= 2 && nodeId === "A1-TOWN-01" && nodes["A1-TOWN-08"] && state.time >= 2 && !state.flags.heard_second_bell) {
      state.flags.heard_second_bell = true;
      state.nodeId = "A1-TOWN-08";
      return { type: "node", id: "A1-TOWN-08" };
    }
    return { type: "node", id: state.nodeId };
  }

  function choose(state, choice, nodes) {
    const notes = [];
    // push return for dialogue/random
    const cur = nodes[state.nodeId];
    if (cur && (cur.kind === "dialogue" || cur.kind === "random" || cur.kind === "hub")) {
      // only push if going into nested content
    }

    let next = choice.next;
    let resultText = "";
    let checkInfo = null;

    if (choice.check) {
      // apply wound disadvantage for STR/DEX/CON
      const check = Object.assign({}, choice.check);
      if (state.flags.wounded && check.stats && check.stats.some((s) => ["STR", "DEX", "CON"].includes(s))) {
        check.disadvantage = true;
      }
      // memory anchor auto-success once
      if (state.flags.memory_anchor_honest && check.stats && check.stats.includes("WIL")) {
        checkInfo = {
          ok: true, total: 99, roll: 20, rolls: [20], dc: check.dc, stat: "WIL",
          modifier: 0, natural: 20, text: "记忆锚点：这次精神检定自动成功。",
        };
        state.flags.memory_anchor_honest = false;
      } else {
        checkInfo = WZCChecks.performCheck(state, check);
      }
      state.lastCheck = checkInfo;
      if (checkInfo.ok) {
        applyEffects(state, choice.success_effects);
        applyEffects(state, choice.effects);
        resultText = choice.success_text || "";
      } else {
        applyEffects(state, choice.fail_effects);
        applyEffects(state, choice.cost_effects);
        resultText = choice.fail_text || "";
      }
      // cost always?
      if (checkInfo.ok && choice.cost_effects && choice.cost_effects.length) {
        applyEffects(state, choice.cost_effects);
      }
    } else {
      applyEffects(state, choice.effects);
      if (choice.flavor && choice.flavor.length) {
        resultText = choice.flavor.join("\n");
      }
    }

    // subchoices without next: effects already in choice; parent next used
    if (!next && choice.subchoices && choice.subchoices.length === 0) {
      next = null;
    }

    // town visit tracking
    if (next && String(next).startsWith("A1-TOWN-") && next !== "A1-TOWN-01") {
      state.town_visits = (state.town_visits || 0) + 1;
      if (state.time < 2) state.time = 2;
      else if (state.town_visits >= 2 && state.time < 3) state.time = 3;
    }
    if (next && String(next).startsWith("CITY-") && next !== "CITY-01") {
      state.city_actions = (state.city_actions || 0) + 1;
      if (state.time < 4) state.time = Math.min(5, state.time + 1);
    }

    if (choice.effects && choice.effects.some((e) => e.op === "ending")) {
      const endId = choice.effects.find((e) => e.op === "ending").key;
      notes.push({ type: "ending", id: endId });
    }

    if (!next) {
      // stay and show result, or stub
      if (cur && cur.default_next) next = cur.default_next;
      else next = state.nodeId; // re-show same node (for hubs after talking)
    }

    const nav = goto(state, next, nodes);
    return { checkInfo, resultText, nav, notes };
  }

  global.WZCEngine = {
    TIME_LABELS,
    createInitialState,
    applyEffects,
    evalCondition,
    filterChoices,
    choose,
    goto,
    woundLevel,
    resonanceLabel,
    get,
    set,
  };
})(typeof window !== "undefined" ? window : globalThis);
