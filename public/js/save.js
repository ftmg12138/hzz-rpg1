(function (global) {
  const PREFIX = "wzc7_";
  const SLOTS = 3;

  function slotKey(i) {
    return PREFIX + (i === 0 ? "auto" : "slot_" + i);
  }

  function listSlots() {
    const out = [];
    for (let i = 1; i <= SLOTS; i++) {
      try {
        const raw = localStorage.getItem(slotKey(i));
        if (!raw) {
          out.push({ index: i, empty: true });
          continue;
        }
        const data = JSON.parse(raw);
        if (data.version !== 2) { out.push({ index: i, empty: true }); continue; }
        out.push({
          index: i,
          empty: false,
          character: data.characterName,
          node: data.nodeId,
          nodeTitle: data.nodeTitle,
          time: data.timeLabel,
          savedAt: data.savedAt,
        });
      } catch (e) {
        out.push({ index: i, empty: true, corrupt: true });
      }
    }
    return out;
  }

  function save(slot, state, meta) {
    const payload = {
      version: 2,
      savedAt: new Date().toISOString(),
      characterName: state.name,
      nodeId: state.node,
      nodeTitle: (meta._nodes && meta._nodes[state.node] && meta._nodes[state.node].title) || state.node,
      timeLabel: (meta.time_labels || [])[Math.min(6, (state.vars && state.vars.time) || 0)] || "",
      state,
    };
    localStorage.setItem(slotKey(slot), JSON.stringify(payload));
    localStorage.setItem(PREFIX + "meta", JSON.stringify({ lastSlot: slot, savedAt: payload.savedAt }));
    return payload;
  }

  function load(slot) {
    const raw = localStorage.getItem(slotKey(slot));
    if (!raw) return null;
    try { const d = JSON.parse(raw); return d && d.version === 2 && d.state ? d : null; } catch (e) { return null; }
  }

  function autosave(state, meta) {
    return save(0, state, meta);
  }
  function loadAutosave() {
    return load(0);
  }

  function getUnlockedEndings() {
    try {
      return JSON.parse(localStorage.getItem(PREFIX + "endings") || "[]");
    } catch {
      return [];
    }
  }
  function unlockEnding(id, title) {
    const list = getUnlockedEndings();
    if (!list.find((e) => e.id === id)) {
      list.push({ id, title, at: new Date().toISOString() });
      localStorage.setItem(PREFIX + "endings", JSON.stringify(list));
    }
  }

  function hasAnySave() {
    if (localStorage.getItem(slotKey(0))) return true;
    for (let i = 1; i <= SLOTS; i++) if (localStorage.getItem(slotKey(i))) return true;
    return false;
  }

  global.WZCSave = {
    SLOTS,
    listSlots,
    save,
    load,
    autosave,
    loadAutosave,
    getUnlockedEndings,
    unlockEnding,
    hasAnySave,
  };
})(typeof window !== "undefined" ? window : globalThis);
