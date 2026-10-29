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

  function hud(s, nodes) {
    const n = nodes[s.node] || {};
    $("hud-name").textContent = s.name;
    $("hud-loc").textContent = n.title || "";
    $("hud-time").textContent = E().timeLabel(s);
    const hp = $("hud-hp"); hp.textContent = `体力 ${s.hp}/${s.max_hp}`; hp.className = s.hp <= Math.ceil(s.max_hp / 3) ? "warn" : "";
    $("hud-vouchers").textContent = `商会券 ${E().num(s, "vouchers")}`;
    const r = E().num(s, "resonance"); const rs = $("hud-resonance");
    rs.textContent = "共鸣 " + "●".repeat(Math.min(r, 6)) + "○".repeat(Math.max(0, 6 - r)); rs.className = r >= 4 ? "warn" : "";
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
    const names = meta.item_names || {};
    const items = s.items.filter((k) => names[k]).map((k) => `<li>${esc(names[k])}</li>`).join("") || "<li>空空如也</li>";
    modal("行囊", `<p>商会券：${E().num(s, "vouchers")} 张</p><ul>${items}</ul>`);
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
  function renderMenu(h) {
    modal("菜单", `<div class="menu"><button type="button" class="btn" id="m-save">存档</button><button type="button" class="btn" id="m-load">读档</button><button type="button" class="btn ghost" id="m-title">回到标题</button></div><p class="hint">检定规则：掷一枚二十面骰，加上相应能力的修正，达到难度即成功。较易 10 · 中等 13 · 困难 16 · 极难 19。</p>`);
    $("m-save").onclick = () => { closeModal(); h.onSave(); };
    $("m-load").onclick = () => { closeModal(); h.onLoad(); };
    $("m-title").onclick = () => { closeModal(); h.onTitle(); };
  }

  global.WZCUI = { toast, renderTitle, renderChars, renderGame, renderJournal, renderBag, renderEndings, renderSaveLoad, renderMenu, closeModal };
})(typeof window !== "undefined" ? window : globalThis);
