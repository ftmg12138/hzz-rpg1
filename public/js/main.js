(async function () {
  const debug = /(?:\?|&)debug=1\b/.test(location.search);
  let meta, nodes, state = null, last = null;

  async function loadData() {
    const [m, n] = await Promise.all([
      fetch("data/meta.json", { cache: "no-cache" }).then((r) => r.json()),
      fetch("data/nodes.json", { cache: "no-cache" }).then((r) => r.json()),
    ]);
    meta = m; nodes = n; meta.debug = debug; meta._nodes = n;
    WZCEngine.init(nodes, meta);
  }

  function persist() { if (state) try { WZCSave.autosave(state, meta); } catch (e) { console.warn(e); } }

  function paint() {
    if (!state || state.node === "__TITLE__") return showTitle();
    WZCUI.renderGame(state, nodes, meta, last, { onChoice, onSub });
  }

  function after(out, fromNode) {
    if (state.node === "__TITLE__") { state = null; last = null; return showTitle(); }
    if (out.subs) { last = { toasts: out.toasts }; }
    else {
      last = { view: { label: out.label, blocks: out.blocks, checkText: out.checkText, ok: out.check ? out.check.ok : null }, toasts: out.toasts, sameNode: state.node === fromNode };
      if (!out.blocks.length && !out.checkText && !out.toasts.length) last = null;
    }
    const n = nodes[state.node];
    if (n && n.kind === "ending") {
      WZCSave.unlockEnding(state.node, n.title);
    }
    for (const t of out.toasts.slice(-1)) WZCUI.toast(t.text);
    persist(); paint();
  }
  function onChoice(c) {
    const from = state.node;
    if (c.next === "__TITLE__" && !c.check) { state = null; last = null; return showTitle(); }
    after(WZCEngine.choose(state, c, null), from);
  }
  function onSub(c) {
    const from = state.node;
    const out = WZCEngine.chooseSub(state, c);
    if (out) after(out, from);
  }

  function showTitle() {
    WZCUI.renderTitle(meta, {
      onNew: () => WZCUI.renderChars(meta, start, showTitle),
      onContinue: () => { const a = WZCSave.loadAutosave(); if (a) { state = a.state; last = null; paint(); } },
      onLoad: openLoad,
      onEndings: () => WZCUI.renderEndings(meta, nodes),
    });
  }
  function start(pc) {
    state = WZCEngine.newState(pc);
    state.seen[state.node] = true;
    last = null; persist(); paint();
  }
  function openSave() {
    if (!state) return WZCUI.toast("没有进行中的旅程");
    WZCUI.renderSaveLoad("save", (slot) => { WZCSave.save(slot, state, meta); WZCUI.toast(`已保存到栏位 ${slot}`); });
  }
  function openLoad() {
    WZCUI.renderSaveLoad("load", (slot) => {
      const d = slot === 0 ? WZCSave.loadAutosave() : WZCSave.load(slot);
      if (!d) return WZCUI.toast("该栏位为空");
      state = d.state; last = null; paint(); WZCUI.toast("进度已读取");
    });
  }

  function bind() {
    document.getElementById("modal-close").onclick = WZCUI.closeModal;
    document.getElementById("overlay").addEventListener("click", (e) => { if (e.target.id === "overlay") WZCUI.closeModal(); });
    document.getElementById("btn-journal").onclick = () => WZCUI.renderJournal(state, meta);
    document.getElementById("btn-bag").onclick = () => WZCUI.renderBag(state, meta);
    document.getElementById("btn-save").onclick = openSave;
    document.getElementById("btn-menu").onclick = () => WZCUI.renderMenu({ onSave: openSave, onLoad: openLoad, onTitle: () => { state = null; showTitle(); } });
    document.addEventListener("keydown", (e) => {
      if (!document.getElementById("overlay").hidden) return;
      const k = Number(e.key); if (!k) return;
      const b = document.querySelectorAll("#screen-game.active #choices .choice")[k - 1];
      if (b && !b.disabled) b.click();
    });
  }

  // 测试钩子（无副作用）
  window.WZC = {
    get state() { return state; }, get nodes() { return nodes; }, get meta() { return meta; },
    start, setRng: (f) => WZCEngine.setRng(f),
  };

  try {
    await WZCGate.requireUnlock();
    await loadData();
    bind();
    showTitle();
  } catch (err) {
    document.body.innerHTML = "<pre style='color:#c97a6a;padding:24px'>加载失败：" + String(err) + "</pre>";
  }
})();
