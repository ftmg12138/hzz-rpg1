(async function () {
  const debug = /(?:\?|&)debug=1\b/.test(location.search);
  let meta, nodes, state;
  let typewriter = false;

  async function loadData() {
    const [m, n] = await Promise.all([
      fetch("data/meta.json").then((r) => r.json()),
      fetch("data/nodes.json").then((r) => r.json()),
    ]);
    meta = m;
    meta.debug = debug;
    meta._nodes = n;
    nodes = n;
  }

  function bindChrome() {
    document.getElementById("modal-close").onclick = () => WZCUI.closeModal();
    document.getElementById("overlay").addEventListener("click", (e) => {
      if (e.target.id === "overlay") WZCUI.closeModal();
    });
    document.getElementById("btn-journal").onclick = () => WZCUI.renderJournal(state);
    document.getElementById("btn-bag").onclick = () => WZCUI.renderBag(state, meta);
    document.getElementById("btn-save").onclick = () => openSave();
    document.getElementById("btn-menu").onclick = () =>
      WZCUI.renderMenu({
        typewriter,
        onSave: openSave,
        onLoad: openLoad,
        onToggleType: () => {
          typewriter = !typewriter;
          WZCUI.toast(typewriter ? "打字机效果已开启（本版立即显示全文，标记已记录）" : "打字机效果已关闭");
        },
        onTitle: () => showTitle(),
      });
  }

  function showTitle() {
    state = null;
    WZCUI.renderTitle(meta, {
      onNew: () => WZCUI.renderChars(meta, startGame, showTitle),
      onContinue: () => {
        const auto = WZCSave.loadAutosave();
        if (auto && auto.state) {
          state = auto.state;
          paint();
          WZCUI.toast("已读取自动存档");
        } else openLoad();
      },
      onLoad: openLoad,
      onEndings: () => WZCUI.renderEndings(meta),
    });
  }

  function startGame(charId) {
    const ch = meta.characters[charId];
    state = WZCEngine.createInitialState(ch);
    // journal seed
    state.journal.push(`以${ch.name}的身份踏入雨夜。`);
    paint();
    persistAuto();
  }

  function paint() {
    if (!state) return showTitle();
    if (state.nodeId === "__TITLE__") return showTitle();
    WZCUI.renderNode(state, meta, nodes, { onChoice });
  }

  function onChoice(choice) {
    if (!state) return;
    // Ending effect on choice going to title
    if (choice.next === "__TITLE__" || (choice.effects || []).some((e) => e.op === "ending")) {
      const endId = (choice.effects || []).find((e) => e.op === "ending")?.key || state.nodeId;
      const title = nodes[endId]?.title || endId;
      WZCSave.unlockEnding(endId, title);
      WZCUI.toast("结局已记录：" + title);
    }

    const result = WZCEngine.choose(state, choice, nodes);
    if (result.checkInfo || result.resultText) {
      state._pendingResult = {
        ok: result.checkInfo ? result.checkInfo.ok : true,
        checkText: result.checkInfo ? result.checkInfo.text : "",
        flavor: result.resultText || "",
      };
    }
    if (result.nav && result.nav.type === "title") {
      showTitle();
      return;
    }
    // death check
    if (state.hp <= 0) {
      const fail = nodes["FAIL-HP"] || nodes["END-05"];
      if (fail) {
        state.nodeId = fail.id;
        state._pendingResult = {
          ok: false,
          checkText: "生命耗尽。",
          flavor: "雨声盖过了一切。",
        };
      }
    }
    persistAuto();
    paint();
  }

  function persistAuto() {
    if (!state) return;
    try {
      WZCSave.autosave(state, meta);
    } catch (e) {
      console.warn(e);
    }
  }

  function openSave() {
    if (!state) {
      WZCUI.toast("没有进行中的旅程");
      return;
    }
    WZCUI.renderSaveLoad("save", state, meta, nodes, (slot) => {
      WZCSave.save(slot, state, meta);
      WZCUI.toast(slot === 0 ? "自动存档已更新" : `已保存到栏位 ${slot}`);
    });
  }

  function openLoad() {
    WZCUI.renderSaveLoad("load", state, meta, nodes, (slot) => {
      const data = slot === 0 ? WZCSave.loadAutosave() : WZCSave.load(slot);
      if (!data || !data.state) {
        WZCUI.toast("该栏位为空");
        return;
      }
      state = data.state;
      paint();
      WZCUI.toast("进度已读取");
    });
  }

  try {
    await loadData();
    bindChrome();
    showTitle();
    console.info(
      `[雾钟城] ${meta.node_count} nodes loaded`,
      debug ? meta.warnings : ""
    );
  } catch (err) {
    document.body.innerHTML =
      "<pre style='color:#c97a6a;padding:24px'>加载失败：" +
      String(err) +
      "\n请确认 data/meta.json 与 data/nodes.json 可访问。</pre>";
  }
})();
