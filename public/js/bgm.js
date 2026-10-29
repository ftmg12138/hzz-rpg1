/*! 雾钟城封面 BGM：Mists in the Elven Lands (Kaiser / The Oracle) · CC0 */
(function (global) {
  const SRC_OGG = "assets/audio/mists-elven-lands.ogg";
  const SRC_MP3 = "assets/audio/mists-elven-lands.mp3";
  const MUTE_KEY = "wzc_bgm_muted";
  const VOL = 0.32;
  const CREDIT =
    "Mists in the Elven Lands · Kaiser / The Oracle · CC0 · OpenGameArt";

  let audio = null;
  let started = false;
  let wantPlay = true;
  let uiBound = false;

  function mutedPref() {
    try {
      return localStorage.getItem(MUTE_KEY) === "1";
    } catch (_) {
      return false;
    }
  }
  function setMutedPref(v) {
    try {
      localStorage.setItem(MUTE_KEY, v ? "1" : "0");
    } catch (_) {}
  }

  function ensureAudio() {
    if (audio) return audio;
    audio = document.createElement("audio");
    audio.id = "wzc-bgm";
    audio.loop = true;
    audio.preload = "none";
    audio.setAttribute("playsinline", "");
    audio.volume = VOL;
    const o = document.createElement("source");
    o.src = SRC_OGG;
    o.type = "audio/ogg; codecs=opus";
    const m = document.createElement("source");
    m.src = SRC_MP3;
    m.type = "audio/mpeg";
    audio.appendChild(o);
    audio.appendChild(m);
    document.body.appendChild(audio);
    return audio;
  }

  function syncToggle() {
    const btn = document.getElementById("bgm-toggle");
    if (!btn) return;
    const muted = mutedPref() || (audio && audio.muted);
    const playing = !!(audio && !audio.paused && started && !muted);
    btn.setAttribute("aria-pressed", muted ? "true" : "false");
    btn.dataset.state = muted ? "muted" : playing ? "playing" : "ready";
    if (muted) {
      btn.innerHTML = "<span class='bgm-ico' aria-hidden='true'>♪</span><span>音乐已静音</span>";
      btn.title = "点击恢复音乐";
    } else if (playing) {
      btn.innerHTML = "<span class='bgm-ico' aria-hidden='true'>♪</span><span>静音</span>";
      btn.title = "静音";
    } else {
      btn.innerHTML = "<span class='bgm-ico' aria-hidden='true'>▶</span><span>点烛听乐</span>";
      btn.title = "播放封面音乐";
    }
  }

  function ensureUI() {
    if (document.getElementById("bgm-toggle")) {
      syncToggle();
      return;
    }
    const wrap = document.createElement("div");
    wrap.id = "bgm-dock";
    wrap.innerHTML = `
      <button type="button" id="bgm-toggle" class="bgm-toggle" aria-pressed="false" title="播放封面音乐">
        <span class="bgm-ico" aria-hidden="true">▶</span><span>点烛听乐</span>
      </button>
      <p class="bgm-credit" id="bgm-credit">${CREDIT}</p>
    `;
    document.body.appendChild(wrap);
    if (!uiBound) {
      uiBound = true;
      document.getElementById("bgm-toggle").addEventListener("click", (e) => {
        e.stopPropagation();
        const a = ensureAudio();
        if (!started || a.paused) {
          setMutedPref(false);
          a.muted = false;
          wantPlay = true;
          tryStart();
          return;
        }
        const next = !mutedPref();
        setMutedPref(next);
        a.muted = next;
        if (next) {
          /* keep playing muted so unmute is instant */
        } else {
          a.play().catch(() => {});
        }
        syncToggle();
      });
    }
    syncToggle();
  }

  function tryStart() {
    ensureUI();
    if (mutedPref()) {
      const a = ensureAudio();
      a.muted = true;
      syncToggle();
      return Promise.resolve(false);
    }
    if (!wantPlay) {
      syncToggle();
      return Promise.resolve(false);
    }
    const a = ensureAudio();
    a.muted = false;
    a.volume = VOL;
    const p = a.play();
    if (p && typeof p.then === "function") {
      return p
        .then(() => {
          started = true;
          syncToggle();
          return true;
        })
        .catch(() => {
          started = false;
          syncToggle();
          return false;
        });
    }
    started = true;
    syncToggle();
    return Promise.resolve(true);
  }

  /** Arm: first user gesture on cover/page starts music (unless muted). */
  function armGestureUnlock(root) {
    ensureUI();
    if (mutedPref()) {
      ensureAudio().muted = true;
      syncToggle();
      return;
    }
    const once = () => {
      tryStart();
    };
    const opts = { capture: true, once: true };
    const targets = [root, document.body].filter(Boolean);
    for (const t of targets) {
      t.addEventListener("pointerdown", once, opts);
      t.addEventListener("keydown", once, opts);
      t.addEventListener("touchstart", once, opts);
    }
  }

  function mount() {
    ensureUI();
    if (mutedPref()) {
      ensureAudio().muted = true;
    }
    syncToggle();
  }

  global.WZCBgm = {
    mount,
    armGestureUnlock,
    tryStart,
    syncToggle,
    CREDIT,
    MUTE_KEY,
  };
})(window);
