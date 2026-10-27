(function (global) {
  const $ = (sel) => document.querySelector(sel);

  function showScreen(id) {
    document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
    const el = document.getElementById(id);
    if (el) el.classList.add("active");
  }

  function toast(msg) {
    const t = $("#toast");
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => { t.hidden = true; }, 2200);
  }

  function openModal(title, html) {
    $("#modal-title").textContent = title;
    $("#modal-body").innerHTML = html;
    $("#overlay").hidden = false;
  }
  function closeModal() {
    $("#overlay").hidden = true;
  }

  function formatText(raw) {
    if (!raw) return "";
    // Escape then light markup
    let s = raw
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    // Speaker tags 【旁白】【内心】【名字】
    s = s.replace(/【旁白】/g, '<span class="speaker">旁白</span> ');
    s = s.replace(/【内心】/g, '<span class="speaker">内心</span> ');
    s = s.replace(/【([^】]+)】/g, '<span class="speaker">$1</span> ');
    // Hide pure development condition lines at start of paragraphs? keep them faded
    s = s.replace(/^〔进入〕.+$/gm, "");
    s = s.replace(/^〔来源〕.+$/gm, '<span class="tag-旁白">$&</span>');
    // Soft-hide 〔效果〕 inline leftover in body
    s = s.replace(/〔效果〕`[^`]+`/g, "");
    // Collapse excess blank lines
    s = s.replace(/\n{3,}/g, "\n\n").trim();
    return s;
  }

  function renderTitle(meta, handlers) {
    showScreen("screen-title");
    const cont = $("#btn-continue");
    cont.hidden = !WZCSave.hasAnySave();
    $("#btn-new").onclick = handlers.onNew;
    cont.onclick = handlers.onContinue;
    $("#btn-load").onclick = handlers.onLoad;
    $("#btn-endings").onclick = handlers.onEndings;
  }

  function renderChars(meta, onPick, onBack) {
    showScreen("screen-chars");
    const grid = $("#char-grid");
    grid.innerHTML = "";
    Object.values(meta.characters).forEach((ch) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "char-card";
      btn.innerHTML = `
        <h3>${ch.name}</h3>
        <div class="role">${ch.title}</div>
        <p class="blurb">${ch.blurb}</p>
        <div class="traits">${(ch.traits || []).map((t) => `<span>${t}</span>`).join("")}</div>
        <p class="blurb" style="margin-top:8px;font-size:12px">残片：${ch.fragment_name || ""}</p>
      `;
      btn.onclick = () => onPick(ch.id);
      grid.appendChild(btn);
    });
    $("#btn-chars-back").onclick = onBack;
  }

  function renderHUD(state, meta, node) {
    $("#hud-name").textContent = state.characterName;
    $("#hud-loc").textContent = node ? node.title : "";
    const tl = (meta.time_labels || WZCEngine.TIME_LABELS)[state.time] || "？";
    $("#hud-time").textContent = "时辰 · " + tl;
    const res = $("#hud-resonance");
    res.textContent = "共鸣 · " + WZCEngine.resonanceLabel(state.resonance);
    if (state.resonance >= 4) res.classList.add("warn"); else res.classList.remove("warn");
    const hp = $("#hud-hp");
    hp.textContent = "伤势 · " + WZCEngine.woundLevel(state);
    const ratio = state.hp / state.max_hp;
    hp.classList.toggle("warn", ratio < 0.5);
    hp.classList.toggle("ok", ratio >= 0.85);
  }

  function renderNode(state, meta, nodes, handlers) {
    showScreen("screen-game");
    const node = nodes[state.nodeId];
    if (!node) {
      $("#node-title").textContent = "迷雾";
      $("#node-text").textContent = "节点缺失：" + state.nodeId;
      return;
    }
    renderHUD(state, meta, node);
    $("#node-title").textContent = node.title;
    const article = $("#node-text");
    article.innerHTML = formatText(node.text);

    const cr = $("#check-result");
    if (state._pendingResult) {
      cr.hidden = false;
      cr.className = "check-result " + (state._pendingResult.ok ? "ok" : "fail");
      let html = "";
      if (state._pendingResult.checkText) html += `<div>${state._pendingResult.checkText}</div>`;
      if (state._pendingResult.flavor) html += `<div style="margin-top:6px">${formatText(state._pendingResult.flavor)}</div>`;
      cr.innerHTML = html;
      state._pendingResult = null;
    } else {
      cr.hidden = true;
      cr.innerHTML = "";
    }

    const box = $("#choices");
    box.innerHTML = "";
    const choices = WZCEngine.filterChoices(state, node);
    if (!choices.length) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "choice";
      b.innerHTML = '<span class="num">→</span>继续';
      b.onclick = () => handlers.onChoice({ next: node.default_next || "__STUB__", effects: [], label: "继续" });
      box.appendChild(b);
    } else {
      choices.forEach((c, idx) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "choice";
        let hint = "";
        if (c.check) {
          hint = `<span class="check-hint">检定 ${c.check.stats.join("/")} · DC ${c.check.dc}</span>`;
        }
        b.innerHTML = `<span class="num">${c.num || idx + 1}.</span>${escapeHtml(c.label)}${hint}`;
        b.onclick = () => {
          if (c.subchoices && c.subchoices.length) {
            openSubchoices(c, handlers);
          } else {
            handlers.onChoice(c);
          }
        };
        box.appendChild(b);
      });
    }

    if (meta.debug) {
      let dbg = document.getElementById("debug-panel");
      if (!dbg) {
        dbg = document.createElement("div");
        dbg.id = "debug-panel";
        dbg.className = "debug";
        box.parentElement.appendChild(dbg);
      }
      dbg.textContent = `node=${state.nodeId} time=${state.time} res=${state.resonance} hp=${state.hp}/${state.max_hp} truth=${state.truth} pressure=${state.fragment_pressure}\nflags=${JSON.stringify(state.flags).slice(0, 300)}`;
    }
  }

  function openSubchoices(choice, handlers) {
    const html = (choice.subchoices || [])
      .map(
        (sc, i) =>
          `<button type="button" class="choice" data-i="${i}"><span class="num">${i + 1}.</span>${escapeHtml(sc.label)}</button>`
      )
      .join("");
    openModal(choice.label, `<div class="choices">${html}</div>`);
    $("#modal-body").querySelectorAll(".choice").forEach((btn) => {
      btn.onclick = () => {
        const sc = choice.subchoices[Number(btn.dataset.i)];
        closeModal();
        // merge sub effects into a synthetic choice
        handlers.onChoice({
          label: sc.label,
          effects: [].concat(choice.effects || [], sc.effects || []),
          check: choice.check,
          success_effects: choice.success_effects,
          fail_effects: choice.fail_effects,
          cost_effects: choice.cost_effects,
          success_text: choice.success_text,
          fail_text: choice.fail_text,
          next: sc.next || choice.next,
          flavor: sc.text ? [sc.text] : choice.flavor,
        });
      };
    });
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function itemLabel(id, meta) {
    return (meta.item_names && meta.item_names[id]) || id;
  }

  function renderBag(state, meta) {
    const items = state.carried.map((id) => `<li>${itemLabel(id, meta)}</li>`).join("") || "<li>（空）</li>";
    const storage = state.storage.map((id) => `<li>${itemLabel(id, meta)}</li>`).join("") || "<li>（空）</li>";
    openModal(
      "行囊",
      `<p>商会券：约 ${state.vouchers} 张（叙事估算）</p>
       <p><strong>随身</strong></p><ul>${items}</ul>
       <p><strong>灰桥仓储</strong></p><ul>${storage}</ul>
       <p style="color:var(--muted);font-size:12px">残片容器无法丢弃；尝试丢弃会在下一场景回到身边。</p>`
    );
  }

  function renderJournal(state) {
    const flags = Object.entries(state.flags)
      .filter(([, v]) => v)
      .map(([k]) => k);
    const clues = flags
      .filter((k) => /clue|truth|map|note|hint|goal|fragment|bone|shadow|cure|writ|safe|freed|warned|saved/i.test(k))
      .slice(0, 40);
    const rels = Object.entries(state.rel)
      .filter(([, v]) => v !== 0)
      .map(([k, v]) => `${k} ${v > 0 ? "+" : ""}${v}`)
      .join(" · ") || "尚无深交";
    openModal(
      "日志与线索",
      `<p><strong>私人目标</strong>：${state.private_goal}（${state.private_goal_state}）</p>
       <p><strong>关系</strong>：${rels}</p>
       <p><strong>倾向</strong>：怜悯 ${state.mercy} · 残忍 ${state.cruelty} · 牺牲 ${state.sacrifice} · 沉沦 ${state.corruption} · 违抗 ${state.defiance}</p>
       <p><strong>已记录线索</strong></p>
       <ul>${clues.map((c) => `<li>${c}</li>`).join("") || "<li>仍在收集中</li>"}</ul>
       <p><strong>访问节点</strong>：${state.visited.length}</p>`
    );
  }

  function renderSaveLoad(mode, state, meta, nodes, handlers) {
    // include autosave as slot 0 display
    const slots = WZCSave.listSlots();
    let html = "";
    if (mode === "save") {
      html += `<div class="slot"><span>自动存档（每次前进覆盖）</span><button type="button" class="btn" data-slot="0">立刻写入</button></div>`;
    } else {
      const auto = WZCSave.loadAutosave();
      if (auto) {
        html += `<div class="slot"><span>自动 · ${auto.characterName} · ${auto.nodeTitle || auto.nodeId}<br/><small>${auto.savedAt}</small></span>
          <button type="button" class="btn primary" data-slot="0">读取</button></div>`;
      }
    }
    for (const s of slots) {
      const label = s.empty
        ? `栏位 ${s.index}（空）`
        : `栏位 ${s.index} · ${s.character} · ${s.nodeTitle || s.node}<br/><small>${s.savedAt}</small>`;
      html += `<div class="slot"><span>${label}</span>
        <button type="button" class="btn ${mode === "save" ? "" : "primary"}" data-slot="${s.index}" ${mode === "load" && s.empty ? "disabled" : ""}>${mode === "save" ? "保存" : "读取"}</button></div>`;
    }
    openModal(mode === "save" ? "保存进度" : "读取存档", html);
    $("#modal-body").querySelectorAll("button[data-slot]").forEach((btn) => {
      btn.onclick = () => {
        const i = Number(btn.dataset.slot);
        closeModal();
        handlers(i);
      };
    });
  }

  function renderEndings(meta) {
    const list = WZCSave.getUnlockedEndings();
    openModal(
      "已见结局",
      list.length
        ? `<ul>${list.map((e) => `<li><strong>${e.title || e.id}</strong><br/><small>${e.at}</small></li>`).join("")}</ul>`
        : "<p>尚未抵达任何结局。灰桥的钟声还在雾里。</p>"
    );
  }

  function renderMenu(handlers) {
    openModal(
      "菜单",
      `<div class="choices">
        <button type="button" class="choice" id="m-save">保存</button>
        <button type="button" class="choice" id="m-load">读取</button>
        <button type="button" class="choice" id="m-type">切换打字机效果（${handlers.typewriter ? "开" : "关"}）</button>
        <button type="button" class="choice" id="m-title">返回标题（不自动保存）</button>
      </div>`
    );
    $("#m-save").onclick = () => { closeModal(); handlers.onSave(); };
    $("#m-load").onclick = () => { closeModal(); handlers.onLoad(); };
    $("#m-type").onclick = () => { closeModal(); handlers.onToggleType(); };
    $("#m-title").onclick = () => { closeModal(); handlers.onTitle(); };
  }

  global.WZCUI = {
    showScreen,
    toast,
    openModal,
    closeModal,
    formatText,
    renderTitle,
    renderChars,
    renderNode,
    renderBag,
    renderJournal,
    renderSaveLoad,
    renderEndings,
    renderMenu,
  };
})(typeof window !== "undefined" ? window : globalThis);
