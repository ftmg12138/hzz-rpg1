/*! 雾钟城封面门禁：口令 + 九点手势（sessionStorage） */
(function (global) {
  const KEY = "wzc_gate_unlocked";
  const MAX_FAIL = 5;
  const LOCK_MS = 30000;
  const MIN_DOTS = 4;

  async function sha256Hex(text) {
    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  function isUnlocked() {
    try { return !!sessionStorage.getItem(KEY); } catch (_) { return false; }
  }
  function markUnlocked(id) {
    try { sessionStorage.setItem(KEY, id || "1"); } catch (_) {}
  }
  function clearUnlocked() {
    try { sessionStorage.removeItem(KEY); } catch (_) {}
  }

  function nearestDot(pad, clientX, clientY) {
    const dots = [...pad.querySelectorAll(".gate-dot")];
    let best = null, bestD = Infinity;
    for (const el of dots) {
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const d = Math.hypot(clientX - cx, clientY - cy);
      const hit = Math.max(r.width, r.height) * 0.72;
      if (d < hit && d < bestD) { bestD = d; best = el; }
    }
    return best;
  }

  function createGateUI() {
    const root = document.createElement("div");
    root.id = "gate";
    root.setAttribute("role", "dialog");
    root.setAttribute("aria-modal", "true");
    root.setAttribute("aria-label", "尘封书封面门禁");
    root.innerHTML = `
      <div class="gate-scene" aria-hidden="true">
        <picture class="gate-photo">
          <source type="image/webp" srcset="assets/gate/tome-desk.webp" />
          <img src="assets/gate/tome-desk.jpg" alt="" width="1502" height="1047" decoding="async" fetchpriority="high" />
        </picture>
        <div class="gate-shade"></div>
        <div class="gate-light" aria-hidden="true"></div>
      </div>
      <div class="gate-plate">
        <p class="gate-eyebrow">尘封典籍</p>
        <h1 class="gate-title">雾钟城：第七声</h1>
        <p class="gate-sub">烛火摇曳。解开封蜡，方可翻开第七声。</p>
        <div class="gate-step" id="gate-step-pass">
          <label class="gate-label" for="gate-pass">口令</label>
          <input type="password" id="gate-pass" class="gate-input" autocomplete="off" spellcheck="false" placeholder="输入口令" />
          <button type="button" class="btn primary gate-btn" id="gate-verify">验证口令</button>
        </div>
        <div class="gate-step" id="gate-step-pat" hidden>
          <p class="gate-label">手势密码 · 至少连四点</p>
          <div class="gate-pad-wrap">
            <svg class="gate-lines" id="gate-lines" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet" aria-hidden="true"></svg>
            <div class="gate-pad" id="gate-pad" role="application" aria-label="九点手势密码">
              ${[1,2,3,4,5,6,7,8,9].map((n) => `<button type="button" class="gate-dot" data-n="${n}" aria-label="点 ${n}" tabindex="-1"></button>`).join("")}
            </div>
          </div>
          <div class="gate-pat-actions">
            <button type="button" class="btn ghost gate-btn-ghost" id="gate-pat-clear">清除手势</button>
            <button type="button" class="btn ghost gate-btn-ghost" id="gate-back-pass">返回口令</button>
          </div>
        </div>
        <p class="gate-msg" id="gate-msg" role="status" aria-live="polite"></p>
        <p class="gate-hint">口令正确后绘制手势 · 本标签页会话内保持解锁</p>
      </div>
    `;
    document.body.appendChild(root);
    document.body.classList.add("gate-locked");
    if (global.WZCBgm) {
      global.WZCBgm.mount();
      global.WZCBgm.armGestureUnlock(root);
    }
    return root;
  }

  function runGate(gateData) {
    return new Promise((resolve) => {
      if (isUnlocked()) {
        document.body.classList.remove("gate-locked");
        if (global.WZCBgm) {
          global.WZCBgm.mount();
          global.WZCBgm.armGestureUnlock(document.body);
        }
        return resolve(true);
      }
      const root = createGateUI();
      const msg = root.querySelector("#gate-msg");
      const passInput = root.querySelector("#gate-pass");
      const stepPass = root.querySelector("#gate-step-pass");
      const stepPat = root.querySelector("#gate-step-pat");
      const pad = root.querySelector("#gate-pad");
      const lines = root.querySelector("#gate-lines");
      const accounts = (gateData && gateData.accounts) || [];

      let failCount = 0;
      let lockUntil = 0;
      let pendingPassword = "";
      let pendingAccount = null;
      let path = [];
      let drawing = false;

      function setMsg(text, kind) {
        msg.textContent = text || "";
        msg.dataset.kind = kind || "";
      }

      function lockedNow() {
        return Date.now() < lockUntil;
      }

      function bumpFail(reason) {
        failCount += 1;
        if (failCount >= MAX_FAIL) {
          lockUntil = Date.now() + LOCK_MS;
          failCount = 0;
          setMsg((reason || "验证失败") + ` · 请 ${Math.ceil(LOCK_MS / 1000)} 秒后再试`, "err");
        } else {
          setMsg((reason || "验证失败") + `（还可试 ${MAX_FAIL - failCount} 次）`, "err");
        }
      }

      function clearPath() {
        path = [];
        pad.querySelectorAll(".gate-dot").forEach((d) => d.classList.remove("on", "active"));
        lines.innerHTML = "";
      }

      function dotCenter(n) {
        const el = pad.querySelector(`.gate-dot[data-n="${n}"]`);
        const pr = pad.getBoundingClientRect();
        const r = el.getBoundingClientRect();
        return {
          x: ((r.left + r.width / 2 - pr.left) / pr.width) * 100,
          y: ((r.top + r.height / 2 - pr.top) / pr.height) * 100,
        };
      }

      function redrawLines(extra) {
        const pts = path.map(dotCenter);
        if (extra) pts.push(extra);
        let html = "";
        for (let i = 1; i < pts.length; i++) {
          const a = pts[i - 1], b = pts[i];
          html += `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" />`;
        }
        lines.innerHTML = html;
      }

      function addDot(el) {
        if (!el) return;
        const n = el.getAttribute("data-n");
        if (path.includes(n)) return;
        path.push(n);
        el.classList.add("on", "active");
        redrawLines();
      }

      async function finishPattern() {
        drawing = false;
        pad.querySelectorAll(".gate-dot.active").forEach((d) => d.classList.remove("active"));
        if (path.length < MIN_DOTS) {
          setMsg(`请至少连接 ${MIN_DOTS} 个点`, "err");
          clearPath();
          return;
        }
        if (lockedNow()) {
          setMsg(`请稍候再试（约 ${Math.ceil((lockUntil - Date.now()) / 1000)} 秒）`, "err");
          clearPath();
          return;
        }
        const pattern = path.join("");
        const gateHash = await sha256Hex(`${pendingPassword}|${pattern}`);
        if (pendingAccount && gateHash === pendingAccount.gate) {
          markUnlocked(pendingAccount.id);
          setMsg("封蜡已启 · 进入雾钟城", "ok");
          root.classList.add("gate-opening");
          setTimeout(() => {
            root.remove();
            document.body.classList.remove("gate-locked");
            if (global.WZCBgm) {
              global.WZCBgm.mount();
              global.WZCBgm.tryStart();
            }
            resolve(true);
          }, 520);
          return;
        }
        bumpFail("手势不正确");
        clearPath();
      }

      function onPointerDown(e) {
        if (stepPat.hidden || lockedNow()) return;
        e.preventDefault();
        drawing = true;
        clearPath();
        const t = e.touches ? e.touches[0] : e;
        addDot(nearestDot(pad, t.clientX, t.clientY));
      }
      function onPointerMove(e) {
        if (!drawing) return;
        e.preventDefault();
        const t = e.touches ? e.touches[0] : e;
        addDot(nearestDot(pad, t.clientX, t.clientY));
        if (path.length) {
          const pr = pad.getBoundingClientRect();
          redrawLines({
            x: ((t.clientX - pr.left) / pr.width) * 100,
            y: ((t.clientY - pr.top) / pr.height) * 100,
          });
        }
      }
      function onPointerUp(e) {
        if (!drawing) return;
        e.preventDefault();
        finishPattern();
      }

      pad.addEventListener("mousedown", onPointerDown);
      window.addEventListener("mousemove", onPointerMove);
      window.addEventListener("mouseup", onPointerUp);
      pad.addEventListener("touchstart", onPointerDown, { passive: false });
      window.addEventListener("touchmove", onPointerMove, { passive: false });
      window.addEventListener("touchend", onPointerUp, { passive: false });

      root.querySelector("#gate-pat-clear").onclick = () => { clearPath(); setMsg(""); };
      root.querySelector("#gate-back-pass").onclick = () => {
        pendingPassword = "";
        pendingAccount = null;
        clearPath();
        stepPat.hidden = true;
        stepPass.hidden = false;
        passInput.value = "";
        setMsg("");
        passInput.focus();
      };

      async function verifyPass() {
        if (lockedNow()) {
          setMsg(`请稍候再试（约 ${Math.ceil((lockUntil - Date.now()) / 1000)} 秒）`, "err");
          return;
        }
        const password = (passInput.value || "").trim();
        if (!password) { setMsg("请输入口令", "err"); return; }
        const passHash = await sha256Hex(password);
        const hit = accounts.find((a) => a.pass === passHash);
        if (!hit) {
          bumpFail("口令不正确");
          passInput.select();
          return;
        }
        pendingPassword = password;
        pendingAccount = hit;
        failCount = 0;
        stepPass.hidden = true;
        stepPat.hidden = false;
        clearPath();
        setMsg("口令已验 · 请绘制手势", "ok");
      }

      root.querySelector("#gate-verify").onclick = verifyPass;
      passInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") verifyPass();
      });
      setTimeout(() => passInput.focus(), 80);
    });
  }

  async function requireUnlock() {
    if (isUnlocked()) {
      document.body.classList.remove("gate-locked");
      if (global.WZCBgm) {
        global.WZCBgm.mount();
        global.WZCBgm.armGestureUnlock(document.body);
      }
      return true;
    }
    let data;
    try {
      data = await fetch("data/gate.json", { cache: "no-cache" }).then((r) => {
        if (!r.ok) throw new Error("gate.json " + r.status);
        return r.json();
      });
    } catch (err) {
      console.error(err);
      document.body.innerHTML = "<pre style='color:#c97a6a;padding:24px'>门禁配置加载失败：" + String(err) + "</pre>";
      throw err;
    }
    return runGate(data);
  }

  global.WZCGate = { requireUnlock, isUnlocked, clearUnlocked, KEY };
})(window);
