/** 雾钟城 v2 界面层 */
(function (global) {
  const $ = (id) => document.getElementById(id);
  const E = () => global.WZCEngine;
  const K = () => global.WZCChecks;

  function esc(t) { return String(t == null ? "" : t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
  function show(id) { document.querySelectorAll(".screen").forEach((el) => el.classList.toggle("active", el.id === id)); window.scrollTo(0, 0); }

  function blockHTML(b, s) {
    if (b.t === "fold") {
      const lab = esc(b.label || "情欲描写");
      const inner = blocksHTML(b.blocks || (b.text ? [{ t: "p", text: b.text }] : []), s);
      if (!inner) return "";
      return `<details class="nsfw-fold"><summary><span class="fold-arrow" aria-hidden="true"></span><span class="fold-label">${lab}</span></summary><div class="fold-body">${inner}</div></details>`;
    }
    const t = esc(b.text);
    if (!t) return "";
    switch (b.t) {
      case "say": return `<p class="b-say">${b.who ? `<span class="speaker">${esc(b.who)}</span>` : ""}<span class="line">${t}</span></p>`;
      case "inner": return `<p class="b-inner">${t}</p>`;
      case "note": return `<p class="b-note">${t}</p>`;
      case "h": return `<h3 class="b-h">${t}</h3>`;
      default: return `<p class="b-p">${t}</p>`;
    }
  }
  function blocksHTML(list, s) {
    return (list || [])
      .filter((b) => !b.cond || !s || E().test(s, b.cond))
      .map((b) => blockHTML(b, s))
      .join("");
  }

  function characterArt(id, name) {
    return `<img class="char-portrait" src="assets/characters/${encodeURIComponent(id)}.jpg" alt="${esc(name)}角色肖像" loading="eager" />`;
  }

  function endingArt(id, title, compact) {
    if (!/^(END|FAIL)-[A-Z0-9-]+$/.test(id || "")) return "";
    const classes = compact ? "ending-art ending-art-compact" : "ending-art";
    return `<img class="${classes}" src="assets/endings/${encodeURIComponent(id)}.jpg" alt="结局《${esc(title)}》象征画" loading="lazy" />`;
  }

  function toast(text) {
    const el = $("toast"); el.textContent = text; el.hidden = false;
    clearTimeout(toast._t); toast._t = setTimeout(() => (el.hidden = true), 2600);
  }

  function renderTitle(meta, h) {
    show("screen-title");
    $("btn-continue").hidden = !global.WZCSave.loadAutosave();
    $("btn-new").onclick = h.onNew; $("btn-continue").onclick = h.onContinue;
    $("btn-load").onclick = h.onLoad; $("btn-endings").onclick = h.onEndings;
  }

  function renderChars(meta, onPick, onBack) {
    show("screen-chars");
    const grid = $("char-grid"); grid.innerHTML = "";
    for (const id of ["edric", "liriel", "thorin"]) {
      const ch = meta.characters[id];
      const b = document.createElement("button");
      b.type = "button"; b.className = "char-card"; b.dataset.pc = id;
      b.innerHTML = characterArt(id, ch.name) + `<span class="char-card-copy"><h3>${esc(ch.name)}</h3><span class="role">${esc(ch.title)}</span><span class="blurb">${esc(ch.blurb)}</span><span class="traits">${(ch.traits || []).map((t) => `<span>${esc(t)}</span>`).join("")}</span></span>`;
      b.onclick = () => onPick(id);
      grid.appendChild(b);
    }
    $("btn-chars-back").onclick = onBack;
  }

  function setVital(el, text, title, warn) {
    if (!el) return;
    el.textContent = text || "";
    if (title) el.title = title;
    el.className = "vital" + (warn ? " warn" : "");
  }
  function hud(s, nodes) {
    const Eng = E();
    if (Eng.ensureBags) Eng.ensureBags(s);
    const meta = global.WZCMeta || {};
    const help = meta.stats_help || {};
    const n = nodes[s.node] || {};
    $("hud-name").textContent = s.name || "";
    $("hud-loc").textContent = n.title || "";
    const time = Eng.timeLabel(s) || "";
    const timeEl = $("hud-time");
    if (timeEl) { timeEl.textContent = time; timeEl.hidden = !time; }
    const hpWarn = s.hp <= Math.ceil(s.max_hp / 3);
    setVital($("hud-hp"), `体 ${s.hp}/${s.max_hp}`, help.hp || "体力", hpWarn);
    setVital($("hud-vouchers"), `券 ${Eng.num(s, "vouchers")}`, help.vouchers || "商会券", false);
    const r = Eng.num(s, "resonance");
    setVital($("hud-resonance"), `共 ${"●".repeat(Math.min(r, 6))}${"○".repeat(Math.max(0, 6 - r))}`, help.resonance || meta.resonance_help || "共鸣", r >= 4);
    const f = Eng.num(s, "fall");
    setVital($("hud-fall"), `沉 ${f}/6`, (help.fall || meta.fall_help || "沉沦") + (Eng.fallLabel ? ` · ${Eng.fallLabel(f)}` : ""), f >= 4);
    const pow = Eng.combatPower ? Eng.combatPower(s) : 0;
    setVital($("hud-power"), `战 ${pow}`, help.power || "战力：装备与属性合计；≥4 战斗占优", pow >= 4);
  }

  function choiceTag(c, s, nodes) {
    const tags = [];
    if (c.check) tags.push((c.check.combat ? "战斗 · " : "") + K().tag(c.check));
    const call = c.call || (c.success && c.success.call);
    if (call && /^C-/.test(call) && !c.check) tags.push("战斗");
    if (c.cost && c.cost.vouchers) tags.push(`花费 ${c.cost.vouchers} 张商会券`);
    if (c.talk) tags.push("交谈");
    if (c.topic) tags.push("话题");
    return tags;
  }

  function renderChoiceList(container, list, s, nodes, onPick) {
    container.innerHTML = "";
    list.forEach((c, i) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "choice"; b.dataset.cid = c.id;
      const afford = E().canAfford(s, c);
      if (!afford) { b.classList.add("locked"); b.disabled = true; }
      const tags = choiceTag(c, s, nodes);
      b.innerHTML = `<span class="num">${i + 1}</span><span class="label">${esc(E().displayLabel(s, c))}</span>` +
        (tags.length ? `<span class="tags">${tags.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</span>` : "");
      b.onclick = () => onPick(c);
      container.appendChild(b);
    });
  }

  function resultHTML(view, toasts, s) {
    if (!view) return "";
    const chips = (toasts || []).map((t) => `<span class="chip ${t.t}">${esc(t.text)}</span>`).join("");
    return `<div class="you-chose">${esc(view.label)}</div>` +
      (view.checkText ? `<div class="check-line ${view.ok ? "ok" : "fail"}">${esc(view.checkText)}</div>` : "") +
      blocksHTML(view.blocks, s) + (chips ? `<div class="chips">${chips}</div>` : "");
  }

  /** last: 上一步的结果 {view, toasts, sameNode} */
  function renderGame(s, nodes, meta, last, h) {
    show("screen-game");
    hud(s, nodes);
    const n = nodes[s.node];
    $("node-title").textContent = n.title;
    $("node-id").textContent = meta.debug ? s.node : "";
    const res = $("result"), text = $("node-text"), status = $("hub-status");
    const pend = E().resolvePending(s);
    // 结果面板
    const view = pend ? pend.view : last && last.view;
    const toasts = last ? last.toasts : [];
    res.innerHTML = resultHTML(view, toasts, s);
    res.hidden = !view;
    if (last && last.extra && last.extra.length) res.innerHTML += blocksHTML(last.extra, s);
    // 节点正文
    let body = blocksHTML(E().blocksFor(s, s.node), s);
    if (n.kind === "ending") {
      body = endingArt(s.node, n.title, false) + body;
      const ep = E().epilogue(s);
      if (ep) body += `<h3 class="b-h">后来</h3>` + blockHTML({ t: "p", text: ep.text });
    }
    const collapse = (pend || (last && last.sameNode)) && n.kind !== "ending";
    text.innerHTML = collapse ? `<details class="reread"><summary>重读此处</summary>${body}</details>` : body;
    // 枢纽状态
    const hb = E().hub(s, n);
    if (hb && !pend && n.kind !== "ending") {
      status.hidden = false;
      status.textContent = hb.h.count_up ? `${hb.h.label} ${hb.count} ${hb.h.unit}` : hb.full ? "时间不多了。" : `${hb.h.label} ${hb.left} ${hb.h.unit}`;
    } else status.hidden = true;
    // 选项
    const box = $("choices");
    if (pend) renderChoiceList(box, pend.subs, s, nodes, (c) => h.onSub(c));
    else renderChoiceList(box, E().visibleChoices(s, s.node), s, nodes, (c) => h.onChoice(c));
  }

  function modal(title, html) { $("modal-title").textContent = title; $("modal-body").innerHTML = html; $("overlay").hidden = false; }
  function closeModal() { $("overlay").hidden = true; }

  function renderJournal(s, meta) {
    if (!s) return;
    const rel = Object.entries(s.vars).filter(([k, v]) => k.startsWith("rel.") && v && E().REL_NAMES[k.slice(4)])
      .map(([k, v]) => `<li>${esc(E().REL_NAMES[k.slice(4)])}：${v >= 2 ? "信任你" : v > 0 ? "对你有好感" : v <= -2 ? "敌视你" : "对你有戒心"}</li>`).join("");
    modal("日志", `<h4>足迹</h4><ul>${s.journal.map((j) => `<li>${esc(j)}</li>`).join("")}</ul>` + (rel ? `<h4>人际</h4><ul>${rel}</ul>` : ""));
  }
  function renderBag(s, meta) {
    if (!s) return;
    const Eng = E();
    if (Eng.ensureBags) Eng.ensureBags(s);
    const names = meta.item_names || {};
    const gear = meta.gear || {};
    const frag = (meta.characters[s.pc] && meta.characters[s.pc].fragment) || null;
    const slotLab = { weapon: "武器", armor: "护甲", magic: "魔具/残片" };
    const atStorage = Eng.canUseStorage && Eng.canUseStorage(s);

    function row(html) { return `<div class="bag-row">${html}</div>`; }
    function btn(label, action, id) {
      return `<button type="button" class="btn tiny" data-act="${action}" data-id="${esc(id || "")}">${esc(label)}</button>`;
    }

    let html = "";
    html += `<div class="bag-equip-head"><h4>装备</h4><span class="bag-power-live" id="bag-power-live">战力 ${Eng.combatPower ? Eng.combatPower(s) : 0}</span></div>`;
    for (const slot of ["weapon", "armor", "magic"]) {
      const id = (s.equip || {})[slot];
      const g = id && gear[id];
      const name = g ? g.name : (names[id] || id || "（空）");
      const pow = g && g.power ? ` · 战力+${g.power}` : "";
      let acts = "";
      if (id && !(slot === "magic" && id === frag)) acts += btn("卸下", "unequip", slot);
      html += row(`<span>${slotLab[slot]}：${esc(name)}${pow}</span>${acts}`);
    }
    const pow = Eng.combatPower ? Eng.combatPower(s) : 0;
    html += row(`<span class="muted">合计战力 ${pow}（≥4 时战斗占优）</span>`);

    const carryMax = Eng.carryCapacity ? Eng.carryCapacity(s) : 8;
    const storageMax = Eng.storageCapacity ? Eng.storageCapacity(s) : 6;
    html += `<h4>行囊 ${s.items.length}/${carryMax}</h4>`;
    if (s.items.length > carryMax) html += `<p class="muted">超载：战力 -2。把物品存入安全点可解除。</p>`;
    html += `<p>商会券：${Eng.num(s, "vouchers")} 张</p>`;
    if (!(s.items || []).length) html += "<p class=\"muted\">（空）</p>";
    (s.items || []).forEach((id) => {
      const g = gear[id];
      const name = g ? g.name : (names[id] || id);
      const pow = g && g.power ? ` ·+${g.power}` : "";
      let acts = "";
      if (g && g.slot) acts += btn("装备", "equip", id);
      if (atStorage && id !== frag) acts += btn("存入安全点", "stash", id);
      html += row(`<span>${esc(name)}${pow}</span>${acts}`);
    });

    html += `<h4>安全点库存 ${(s.storage || []).length}/${storageMax}</h4>`;
    if (!(s.storage || []).length) html += "<p class=\"muted\">（空）</p>";
    (s.storage || []).forEach((id) => {
      const g = gear[id];
      const name = g ? g.name : (names[id] || id);
      html += row(`<span>${esc(name)}</span>${atStorage ? btn("取回", "take", id) : ""}`);
    });
    if (!atStorage) html += `<p class="muted">存取需回到白鸦旅店安全点。</p>`;
    if (s.node === "A1-STASH-01") html += `<p class="muted">东仓出发前已存 ${Eng.num(s, "warehouse_stashed")}/2 件。</p>`;

    html += "<h4>状态</h4>";
    const f = Eng.num(s, "fall");
    html += row(`<span>${Eng.fallLabel ? Eng.fallLabel(f) : "沉沦"}（${f}/6）</span>`);
    html += row(`<span>残片压迫 ${Eng.num(s, "fragment_pressure")} · 共鸣 ${Eng.num(s, "resonance")} · 真相 ${Eng.num(s, "truth")}</span>`);
    if (s.vars.companion) html += row(`<span>同伴：${esc((meta.characters[s.vars.companion] || {}).name || String(s.vars.companion))}</span>`);

    modal("行囊与装备", html);
    document.querySelectorAll("#modal-body [data-act]").forEach((b) => {
      b.onclick = () => {
        const act = b.dataset.act, id = b.dataset.id;
        let r;
        if (act === "equip") r = Eng.equipItem(s, id);
        else if (act === "unequip") r = Eng.unequipSlot(s, id);
        else if (act === "stash") r = Eng.stashItem(s, id);
        else if (act === "take") r = Eng.takeStash(s, id);
        if (r) toast(r.text);
        if (r && r.ok && global.WZCSave) global.WZCSave.autosave(s, meta);
        renderBag(s, meta);
        // refresh HUD if game screen visible
        const loc = $("hud-loc");
        if (loc && global.WZC && WZC.state) {
          /* paint via re-hud only — avoid full repaint stealing focus */
          try { hud(WZC.state, WZC.nodes); } catch (e) {}
        }
      };
    });
  }
  function renderEndings(meta, nodes) {
    const list = global.WZCSave.getUnlockedEndings();
    modal("已见结局", list.length ? `<div class="ending-gallery">${list.map((e) => `<article class="ending-card">${endingArt(e.id, e.title, true)}<span>${esc(e.title)}</span></article>`).join("")}</div>` : "<p>还没有见过任何结局。</p>");
  }
  function renderSaveLoad(mode, onPick) {
    const slots = global.WZCSave.listSlots();
    const rows = slots.map((sl) => `<div class="slot"><div>栏位 ${sl.index}<br><small>${sl.empty ? "空" : esc(`${sl.character} · ${sl.nodeTitle} · ${sl.time}`)}</small></div><button type="button" class="btn" data-slot="${sl.index}" ${mode === "load" && sl.empty ? "disabled" : ""}>${mode === "save" ? "保存" : "读取"}</button></div>`).join("");
    const auto = mode === "load" && global.WZCSave.loadAutosave() ? `<div class="slot"><div>自动存档</div><button type="button" class="btn" data-slot="0">读取</button></div>` : "";
    modal(mode === "save" ? "存档" : "读档", auto + rows);
    document.querySelectorAll("#modal-body [data-slot]").forEach((b) => (b.onclick = () => { onPick(Number(b.dataset.slot)); closeModal(); }));
  }
  function renderStatsHelp(focus) {
    const meta = global.WZCMeta || {};
    const h = meta.stats_help || {};
    const order = [
      ["hp", "体力", h.hp || meta.hp_help],
      ["vouchers", "商会券", h.vouchers || meta.vouchers_help],
      ["resonance", "共鸣", h.resonance || meta.resonance_help],
      ["fall", "沉沦", h.fall || meta.fall_help],
      ["power", "战力", h.power || meta.power_help],
      ["fragment_pressure", "残片压迫", h.fragment_pressure],
      ["truth", "真相", h.truth],
    ];
    let body = `<dl class="stats-help">`;
    for (const [k, label, text] of order) {
      if (!text) continue;
      const hi = focus && focus === k ? ` style="color:var(--ember)"` : "";
      body += `<dt${hi}>${esc(label)}</dt><dd>${esc(text)}</dd>`;
    }
    body += `</dl><p class="muted">点顶部状态条任一格也可打开本说明。正文里的「▸ 残片侵扰 / ▸ 情欲描写」可展开压迫细节。</p>`;
    modal("属性说明", body);
  }
  function renderMenu(h) {
    modal("菜单", `<div class="menu"><button type="button" class="btn" id="m-save">存档</button><button type="button" class="btn" id="m-load">读档</button><button type="button" class="btn ghost" id="m-help">属性说明</button><button type="button" class="btn ghost" id="m-title">回到标题</button></div><p class="hint">检定规则：掷一枚二十面骰，加上相应能力的修正，达到难度即成功。较易 10 · 中等 13 · 困难 16 · 极难 19。</p>`);
    $("m-save").onclick = () => { closeModal(); h.onSave(); };
    $("m-load").onclick = () => { closeModal(); h.onLoad(); };
    $("m-help").onclick = () => renderStatsHelp();
    $("m-title").onclick = () => { closeModal(); h.onTitle(); };
  }


  function dossierDepth(s, id) {
    const d = Number(s.vars["dossier_" + id + "_depth"] || 0);
    if (s.pc === id) return Math.max(d, 2);
    const met = !!(s.vars["met_" + id] || s.vars[id + "_met"] || s.vars["talked_" + id]);
    if (id === "kael") return met || s.seen["A1-TOWN-02"] || s.seen["A1-TOWN-01"] ? Math.max(d, 0) : -1;
    if (!met) return -1;
    return Math.max(d, 0);
  }
  function renderPeople(s, meta) {
    if (!s) return;
    const dossiers = meta.dossiers || {};
    const order = [s.pc, "edric","liriel","thorin","valen","kael","ysolde","mira","eilyn","mara","garrick","elara","serath","lyra","gromm"];
    const seen = new Set();
    let html = "<p class=\"muted\">点开条目可查看外貌、性格与你目前所知的经历。</p>";
    let shown = 0;
    order.forEach((id) => {
      if (!id || seen.has(id)) return; seen.add(id);
      const d = dossiers[id]; if (!d) return;
      const depth = dossierDepth(s, id);
      if (depth < 0) return;
      shown++;
      const hist = d["history" + Math.min(Math.max(depth, 0), 2)] || d.history0 || "";
      const tag = id === s.pc ? "主角" : (d.role || (d.appear ? d.appear.slice(0, 14) : id));
      html += `<details class="dossier"${id === s.pc ? " open" : ""}><summary>${esc(d.name)} · ${esc(tag)}</summary>` +
        `<div class="dossier-body">` +
        (d.appear ? `<p><strong>外貌</strong> — ${esc(d.appear)}</p>` : "") +
        (d.personality ? `<p><strong>性格</strong> — <em>${esc(d.personality)}</em></p>` : "") +
        (d.blurb ? `<p>${esc(d.blurb)}</p>` : "") +
        (id === "edric" || id === "liriel" || id === "thorin" ? `<p><strong>沉沦</strong> — ${esc(s.vars["fall_" + id] || 0)}/6</p>` : "") +
        `<p class="muted"><strong>已知经历</strong> — ${esc(hist || d.known || "初识。")}</p>` +
        `</div></details>`;
    });
    if (!shown) html = "<p class=\"muted\">尚未结识足够的人。去酒馆或街口多开口。</p>";
    modal("人物简介", html);
  }
  global.WZCUI = { toast, renderTitle, renderChars, renderGame, renderJournal, renderBag, renderPeople, renderEndings, renderSaveLoad, renderMenu, renderStatsHelp, closeModal };
})(typeof window !== "undefined" ? window : globalThis);
