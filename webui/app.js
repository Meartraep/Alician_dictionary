(() => {
  const APP_IDS = ["dictionary", "writing", "dbmanager", "settings"];
  const DETACHABLE_APP_IDS = ["dictionary", "writing", "dbmanager"];
  const APP_TITLES = {
    dictionary: "词典工具",
    writing: "写作助手",
    dbmanager: "数据库管理",
    settings: "设置",
  };

  const STORAGE_KEYS = {
    dictLeft: "ui.dict.leftRatio",
    writingMain: "ui.writing.mainRatio",
    writingTop: "ui.writing.topRatio",
    dictSnapshot: "ui.dictionary.snapshot",
    writingSnapshot: "ui.writing.snapshot",
  };

  function getWindowParams() {
    const source = window.location.search || window.location.hash.replace(/^#/, "");
    return new URLSearchParams(source);
  }

  const WINDOW_PARAMS = getWindowParams();
  const NATIVE_APP_ID = WINDOW_PARAMS.get("app");
  const IS_NATIVE_DETACHED = WINDOW_PARAMS.get("window") === "detached" && DETACHABLE_APP_IDS.includes(NATIVE_APP_ID);

  const state = {
    isNativeDetached: IS_NATIVE_DETACHED,
    nativeAppId: IS_NATIVE_DETACHED ? NATIVE_APP_ID : null,
    activeDocked: "dictionary",
    zIndexSeed: 30,
    dragTabAppId: null,
    apps: {
      dictionary: { detached: false, floatingWindow: null },
      writing: { detached: false, floatingWindow: null },
      dbmanager: { detached: false, floatingWindow: null },
      settings: { detached: false, floatingWindow: null },
    },
    dbmanager: {
      currentTable: "",
      tables: [],
      fields: [],
      data: [],
      selectedIds: new Set(),
      globalResults: [],
    },
    dictionary: {
      currentExamplesPayload: null,
      historyVisible: false,
    },
    writing: {
      debounceTimer: null,
      checkSeq: 0,
      appliedSeq: 0,
      lastResult: null,
      settings: { strict_case: true, max_undo_steps: 100, excluded_words: [] },
      selectedSidebarKey: "",
      infoPopup: null,
      isComposing: false,
    },
    settings: {
      autoUpdate: true,
      status: "",
    },
  };

  const els = {};

  function escapeHtml(raw) {
    return String(raw)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function escapeRegExp(text) {
    return String(text).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function saveRatio(key, value) {
    try {
      localStorage.setItem(key, String(value));
    } catch (_) {
      // ignore
    }
  }

  function loadRatio(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      if (raw == null) return fallback;
      const val = Number(raw);
      return Number.isFinite(val) ? val : fallback;
    } catch (_) {
      return fallback;
    }
  }

  function saveJson(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (_) {
      // ignore
    }
  }

  function loadJson(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (_) {
      return fallback;
    }
  }

  let pywebviewApiReady = null;

  function getPywebviewApi() {
    const api = window.pywebview?.api;
    return api && typeof api === "object" ? api : null;
  }

  function waitForPywebviewApi(timeoutMs = 8000) {
    const current = getPywebviewApi();
    if (current) return Promise.resolve(current);
    if (pywebviewApiReady) return pywebviewApiReady;

    pywebviewApiReady = new Promise((resolve, reject) => {
      let settled = false;
      let pollTimer = null;
      let timeoutTimer = null;

      const cleanup = () => {
        window.removeEventListener("pywebviewready", onReady);
        if (pollTimer !== null) window.clearInterval(pollTimer);
        if (timeoutTimer !== null) window.clearTimeout(timeoutTimer);
      };

      const finish = (api, error = null) => {
        if (settled) return;
        settled = true;
        cleanup();
        pywebviewApiReady = error ? null : Promise.resolve(api);
        if (error) {
          reject(error);
          return;
        }
        resolve(api);
      };

      const checkReady = () => {
        const api = getPywebviewApi();
        if (api) finish(api);
      };

      const onReady = () => {
        checkReady();
      };

      window.addEventListener("pywebviewready", onReady);
      pollTimer = window.setInterval(checkReady, 50);
      timeoutTimer = window.setTimeout(() => {
        finish(null, new Error("Python API unavailable"));
      }, timeoutMs);

      checkReady();
    });

    return pywebviewApiReady;
  }

  async function waitForPywebviewMethod(method, timeoutMs = 8000) {
    const started = Date.now();
    let api = await waitForPywebviewApi(timeoutMs);
    while (Date.now() - started < timeoutMs) {
      const fn = api?.[method];
      if (typeof fn === "function") return fn.bind(api);
      await new Promise((resolve) => window.setTimeout(resolve, 50));
      api = getPywebviewApi() || api;
    }
    throw new Error(`Python API method unavailable: ${method}`);
  }

  async function callApi(method, ...args) {
    const fn = await waitForPywebviewMethod(method);
    return fn(...args);
  }

  function toast(message, kind = "info", duration = 2200) {
    const node = document.createElement("div");
    node.className = `toast ${kind}`;
    node.textContent = message;
    els.toastRoot.appendChild(node);
    setTimeout(() => node.remove(), duration);
  }

  function bindBaseElements() {
    const ids = [
      "tabBar", "workspace", "dockHost", "floatingLayer",
      "modalRoot", "modalTitle", "modalBody", "modalCloseBtn", "toastRoot",
      "dictLayout", "dictSplit", "dictQuery", "dictExact", "dictSearchBtn", "dictHistoryBtn", "dictHistory", "dictResults", "dictExamples",
      "writingWorkspace", "writingTop", "writingMainSplit", "writingBottomSplit", "writingEditor", "writingSidebar", "writingStatus", "writingExplanation",
      "writingImportBtn", "writingExportBtn", "writingSettingsBtn", "writingSettingsPanel",
      "writingDictQuery", "writingDictExact", "writingDictSearchBtn",
      "settingsStrictCase", "settingsUndo", "excludedInput", "excludedAddBtn", "excludedList", "settingsSaveBtn", "settingsCloseBtn",
      "autoUpdateToggle", "autoUpdateStatus",
      "dbmTableList", "dbmRefreshBtn", "dbmSearchInput", "dbmSearchBtn",
      "dbmShowAllBtn", "dbmAddBtn", "dbmEditBtn", "dbmDeleteBtn",
      "dbmDataTable", "dbmStatus", "dbmGlobalSearchInput",
      "dbmGlobalSearchBtn", "dbmReplaceInput", "dbmReplaceBtn",
      "dbmGlobalStatus",
      "fileLoader",
    ];
    for (const id of ids) els[id] = document.getElementById(id);
  }

  function configureWindowMode() {
    if (!state.isNativeDetached) return;
    document.body.classList.add("native-detached-window");
    state.activeDocked = state.nativeAppId;
    for (const appId of APP_IDS) {
      if (appId !== state.nativeAppId) {
        state.apps[appId].detached = true;
      }
    }
  }

  function showModal(title, html, onBind) {
    els.modalTitle.textContent = title;
    els.modalBody.innerHTML = html;
    els.modalRoot.classList.remove("hidden");
    if (onBind) onBind();
  }

  function closeModal() {
    els.modalRoot.classList.add("hidden");
    els.modalBody.innerHTML = "";
  }

  function getTabButton(appId) {
    return els.tabBar.querySelector(`.tab-item[data-app="${appId}"]`);
  }

  function getAppPanel(appId) {
    return document.getElementById(`panel-${appId}`);
  }

  function renderDockPanels() {
    if (state.isNativeDetached) {
      for (const appId of APP_IDS) {
        const panel = getAppPanel(appId);
        panel.classList.toggle("show", appId === state.nativeAppId);
      }
      return;
    }

    for (const appId of APP_IDS) {
      const panel = getAppPanel(appId);
      panel.classList.toggle("show", !state.apps[appId].detached && state.activeDocked === appId);
    }
  }

  function updateTabVisualState() {
    if (state.isNativeDetached) return;
    for (const appId of APP_IDS) {
      const tab = getTabButton(appId);
      tab.classList.toggle("detached", state.apps[appId].detached);
      tab.classList.toggle("active", !state.apps[appId].detached && state.activeDocked === appId);
    }
  }

  function activateDocked(appId) {
    if (state.isNativeDetached) return;
    if (state.apps[appId].detached) {
      const win = state.apps[appId].floatingWindow;
      if (win) bringFloatingToFront(win);
      return;
    }
    state.activeDocked = appId;
    renderDockPanels();
    updateTabVisualState();
  }

  function bringFloatingToFront(win) {
    state.zIndexSeed += 1;
    win.style.zIndex = String(state.zIndexSeed);
  }

  function chooseNextDockedApp(exceptAppId) {
    return APP_IDS.find((id) => id !== exceptAppId && !state.apps[id].detached) || null;
  }

  function saveModuleSnapshot(appId) {
    if (appId === "dictionary") {
      saveJson(STORAGE_KEYS.dictSnapshot, {
        query: els.dictQuery?.value || "",
        exact: Boolean(els.dictExact?.checked),
      });
      return;
    }
    if (appId === "writing") {
      saveJson(STORAGE_KEYS.writingSnapshot, {
        text: getEditorText(),
        dictQuery: els.writingDictQuery?.value || "",
        dictExact: Boolean(els.writingDictExact?.checked),
      });
    }
  }

  async function detachAppToNativeWindow(appId, event) {
    if (state.isNativeDetached || !DETACHABLE_APP_IDS.includes(appId) || state.apps[appId]?.detached) return;
    saveModuleSnapshot(appId);
    try {
      const ret = await callApi("detach_native_window", appId, Math.round(event.screenX), Math.round(event.screenY));
      toast(ret?.message || "已打开独立窗口。", ret?.ok ? "info" : "warn");
      if (!ret?.ok) return;
      state.apps[appId].detached = true;
      state.apps[appId].floatingWindow = null;
      if (state.activeDocked === appId) {
        state.activeDocked = chooseNextDockedApp(appId) || appId;
      }
      renderDockPanels();
      updateTabVisualState();
    } catch (err) {
      toast(`打开独立窗口失败：${err.message}`, "warn", 3200);
    }
  }

  window.__nativeAppReturned = (appId) => {
    if (!APP_IDS.includes(appId)) return;
    state.apps[appId].detached = false;
    state.apps[appId].floatingWindow = null;
    state.activeDocked = appId;
    renderDockPanels();
    updateTabVisualState();
    restoreModuleSnapshot(appId, true);
  };

  function bindFloatingDragging(win, head, appId) {
    let dragging = false;
    let dx = 0;
    let dy = 0;

    head.addEventListener("mousedown", (e) => {
      if (e.target.tagName === "BUTTON") return;
      dragging = true;
      bringFloatingToFront(win);
      const rect = win.getBoundingClientRect();
      dx = e.clientX - rect.left;
      dy = e.clientY - rect.top;
      e.preventDefault();
    });

    window.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      const x = e.clientX - dx;
      const y = e.clientY - dy;
      win.style.left = `${x}px`;
      win.style.top = `${y}px`;
    });

    window.addEventListener("mouseup", (e) => {
      if (!dragging) return;
      dragging = false;
      const tr = els.tabBar.getBoundingClientRect();
      const inTabBar = e.clientX >= tr.left && e.clientX <= tr.right && e.clientY >= tr.top && e.clientY <= tr.bottom;
      if (inTabBar) attachAppToDock(appId, true);
    });
  }

  function createFloatingWindow(appId, left, top) {
    const win = document.createElement("div");
    win.className = "floating-window";
    win.style.left = `${left}px`;
    win.style.top = `${top}px`;

    const head = document.createElement("div");
    head.className = "window-head";
    head.innerHTML = `<span>${APP_TITLES[appId]}</span>`;
    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.textContent = "关闭并归位";
    head.appendChild(closeBtn);
    win.appendChild(head);

    const body = document.createElement("div");
    body.className = "window-body";
    win.appendChild(body);

    closeBtn.addEventListener("click", () => attachAppToDock(appId, true));
    win.addEventListener("mousedown", () => bringFloatingToFront(win));
    bindFloatingDragging(win, head, appId);
    return { win, body };
  }

  function detachAppFromDock(appId, clientX, clientY) {
    if (state.apps[appId].detached) return;
    const { win, body } = createFloatingWindow(appId, clientX - 160, clientY - 40);
    const panel = getAppPanel(appId);
    panel.classList.add("show");
    body.appendChild(panel);
    els.floatingLayer.appendChild(win);

    state.apps[appId].detached = true;
    state.apps[appId].floatingWindow = win;
    if (state.activeDocked === appId) {
      state.activeDocked = APP_IDS.find((id) => !state.apps[id].detached && id !== appId) || "dictionary";
    }
    renderDockPanels();
    updateTabVisualState();
    bringFloatingToFront(win);
  }

  function attachAppToDock(appId, shouldActivate = true) {
    const info = state.apps[appId];
    if (!info.detached) {
      if (shouldActivate) activateDocked(appId);
      return;
    }
    const panel = getAppPanel(appId);
    els.dockHost.appendChild(panel);
    panel.classList.toggle("show", shouldActivate);
    if (info.floatingWindow) info.floatingWindow.remove();
    info.detached = false;
    info.floatingWindow = null;
    if (shouldActivate) state.activeDocked = appId;
    renderDockPanels();
    updateTabVisualState();
  }

  function bindTabs() {
    if (state.isNativeDetached) return;
    const tabs = els.tabBar.querySelectorAll(".tab-item");
    tabs.forEach((tab) => {
      const appId = tab.dataset.app;
      tab.draggable = DETACHABLE_APP_IDS.includes(appId);
      tab.addEventListener("click", () => activateDocked(appId));
      if (!DETACHABLE_APP_IDS.includes(appId)) return;
      tab.addEventListener("dragstart", () => {
        state.dragTabAppId = appId;
      });
      tab.addEventListener("dragend", (e) => {
        const id = state.dragTabAppId;
        state.dragTabAppId = null;
        if (!id) return;
        const tr = els.tabBar.getBoundingClientRect();
        const inTabBar = e.clientX >= tr.left && e.clientX <= tr.right && e.clientY >= tr.top && e.clientY <= tr.bottom;
        if (!inTabBar) detachAppToNativeWindow(id, e);
      });
    });
  }

  function bindSplitters() {
    document.documentElement.style.setProperty("--dict-left", `${clamp(loadRatio(STORAGE_KEYS.dictLeft, 50), 15, 85)}%`);
    document.documentElement.style.setProperty("--writing-main", `${clamp(loadRatio(STORAGE_KEYS.writingMain, 68), 25, 90)}%`);
    document.documentElement.style.setProperty("--writing-top", `${clamp(loadRatio(STORAGE_KEYS.writingTop, 72), 20, 90)}%`);

    const startDrag = (splitterEl, onMove) => {
      splitterEl.addEventListener("mousedown", (e) => {
        if (e.button !== 0) return;
        e.preventDefault();
        document.body.classList.add("splitter-active");
        const move = (evt) => onMove(evt);
        const up = () => {
          document.body.classList.remove("splitter-active");
          window.removeEventListener("mousemove", move);
          window.removeEventListener("mouseup", up);
        };
        window.addEventListener("mousemove", move);
        window.addEventListener("mouseup", up);
      });
    };

    const isNarrowLayout = () => window.matchMedia("(max-width: 980px)").matches;

    startDrag(els.dictSplit, (evt) => {
      const rect = els.dictLayout.getBoundingClientRect();
      const rawRatio = isNarrowLayout()
        ? ((evt.clientY - rect.top) / rect.height) * 100
        : ((evt.clientX - rect.left) / rect.width) * 100;
      const ratio = clamp(rawRatio, 15, 85);
      document.documentElement.style.setProperty("--dict-left", `${ratio}%`);
      saveRatio(STORAGE_KEYS.dictLeft, ratio);
    });

    startDrag(els.writingMainSplit, (evt) => {
      const rect = els.writingTop.getBoundingClientRect();
      const rawRatio = isNarrowLayout()
        ? ((evt.clientY - rect.top) / rect.height) * 100
        : ((evt.clientX - rect.left) / rect.width) * 100;
      const ratio = clamp(rawRatio, 25, 90);
      document.documentElement.style.setProperty("--writing-main", `${ratio}%`);
      saveRatio(STORAGE_KEYS.writingMain, ratio);
    });

    startDrag(els.writingBottomSplit, (evt) => {
      const rect = els.writingWorkspace.getBoundingClientRect();
      const ratio = clamp(((evt.clientY - rect.top) / rect.height) * 100, 20, 90);
      document.documentElement.style.setProperty("--writing-top", `${ratio}%`);
      saveRatio(STORAGE_KEYS.writingTop, ratio);
    });
  }

  function applyWordHighlight(text, word) {
    const source = String(text || "");
    const target = String(word || "").trim();
    if (!target) return escapeHtml(source);
    const regex = new RegExp(`\\b${escapeRegExp(target)}\\b`, "gi");
    let output = "";
    let last = 0;
    let match = regex.exec(source);
    while (match) {
      output += escapeHtml(source.slice(last, match.index));
      output += `<mark class="lyric-word-hit">${escapeHtml(match[0])}</mark>`;
      last = match.index + match[0].length;
      match = regex.exec(source);
    }
    output += escapeHtml(source.slice(last));
    return output;
  }

  function renderLyricWithFocus(lyric, word, start, end) {
    const full = String(lyric || "");
    const s = clamp(Number(start || 0), 0, full.length);
    const e = clamp(Number(end || 0), s, full.length);
    const before = full.slice(0, s);
    const focused = full.slice(s, e);
    const after = full.slice(e);
    const focusHtml = focused
      ? `<span class="lyric-paragraph-focus">${applyWordHighlight(focused, word)}</span>`
      : "";
    return `${applyWordHighlight(before, word)}${focusHtml}${applyWordHighlight(after, word)}`;
  }

  async function runDictionarySearch(query, exactMatch) {
    const q = String(query ?? els.dictQuery.value).trim();
    if (!q) return toast("请输入要查询的词。", "warn");
    const exact = Boolean(exactMatch ?? els.dictExact.checked);
    saveJson(STORAGE_KEYS.dictSnapshot, { query: q, exact });
    try {
      const ret = await callApi("dictionary_search", q, exact);
      renderDictionaryResults(ret);
    } catch (err) {
      toast(`查询失败：${err.message}`, "warn", 3200);
    }
  }

  function renderDictionaryHistory(history) {
    const list = Array.isArray(history) ? history : [];
    if (!list.length) {
      els.dictHistory.innerHTML = '<div class="history-item">暂无历史记录</div>';
      return;
    }
    els.dictHistory.innerHTML = list
      .map((item) => `<div class="history-item" data-query="${escapeHtml(item)}">${escapeHtml(item)}</div>`)
      .join("");
  }

  function renderDictionaryResults(payload) {
    const sections = payload?.sections || [];
    if (!sections.length) {
      els.dictResults.innerHTML = `<div class="result-item">${escapeHtml(payload?.message || "未找到结果")}</div>`;
      renderDictionaryHistory(payload?.history || []);
      return;
    }

    els.dictResults.innerHTML = sections
      .map((sec) => {
        const rows = (sec.entries || []).map((entry) => `
          <div class="result-item">
            <div class="result-main">${escapeHtml(entry.word || "")}</div>
            <div class="result-meta">
              ${(entry.word_class || "词类未知")} | 词频: ${entry.count ?? 0} | 泛度: ${entry.variety ?? 0}
            </div>
            <div class="example-paragraph">${escapeHtml(entry.explanation || "")}</div>
            <div class="result-actions">
              <button class="small dict-example-btn" type="button" data-word="${escapeHtml(entry.word || "")}">显示例句</button>
            </div>
          </div>
        `).join("");
        return `
          <section class="result-section">
            <div class="result-section-title">${escapeHtml(sec.title || "")}</div>
            ${rows}
          </section>
        `;
      })
      .join("");
    renderDictionaryHistory(payload?.history || []);
  }

  async function loadDictionaryExamples(word) {
    const target = String(word || "").trim();
    if (!target) return;
    try {
      const ret = await callApi("dictionary_examples", target);
      state.dictionary.currentExamplesPayload = ret;
      renderDictionaryExamples(ret);
    } catch (err) {
      toast(`加载例句失败：${err.message}`, "warn", 3200);
    }
  }

  function renderDictionaryExamples(payload) {
    const examples = payload?.examples || [];
    if (!examples.length) {
      els.dictExamples.innerHTML = `<div class="example-item">${escapeHtml(payload?.message || "无例句")}</div>`;
      return;
    }
    const word = payload.word || "";
    els.dictExamples.innerHTML = examples
      .map((ex, idx) => `
        <div class="example-item">
          <div class="example-source">${escapeHtml(ex.album || "")} - ${escapeHtml(ex.title || "")}</div>
          <div class="example-paragraph">${applyWordHighlight(ex.paragraph || "", word)}</div>
          <div class="result-actions">
            <button class="small dict-context-btn" type="button" data-index="${idx}">查看上下文</button>
          </div>
        </div>
      `)
      .join("");
  }

  function openLyricContext(payload, sourceIndex) {
    const allExamples = payload?.examples || [];
    if (!allExamples.length || sourceIndex < 0 || sourceIndex >= allExamples.length) return;

    let currentIndex = sourceIndex;
    const originalTotal = Number(payload?.total_before || allExamples.length);
    const dedupRate = Number(payload?.deduplication_rate ?? 0);
    const songStats = Array.isArray(payload?.song_stats) ? payload.song_stats : [];

    showModal("例句上下文", `
      <div class="stats-box">
        <div class="result-section-title">例句来源统计</div>
        <div id="lyricStats"></div>
      </div>
      <div class="stats-box">
        <div id="lyricSongTitle">当前歌曲</div>
      </div>
      <div class="result-actions" style="margin-bottom: 8px;">
        <button id="lyricPrevBtn" class="ghost" type="button">上一句</button>
        <div id="lyricCounter" style="padding: 7px 10px;"></div>
        <button id="lyricNextBtn" class="ghost" type="button">下一句</button>
      </div>
      <div id="lyricView" class="lyric-view"></div>
      <div class="result-actions">
        <button id="lyricEditBtn" type="button">编辑歌词</button>
        <button id="lyricSaveBtn" type="button" class="hidden">保存歌词</button>
        <button id="lyricCancelBtn" type="button" class="ghost hidden">取消编辑</button>
      </div>
      <div id="lyricEditWrap" class="hidden">
        <div class="panel-subtitle">编辑模式：修改整首歌词后点击“保存歌词”</div>
        <textarea id="lyricEditor" class="lyric-area"></textarea>
      </div>
    `, () => {
      const statsEl = document.getElementById("lyricStats");
      const titleEl = document.getElementById("lyricSongTitle");
      const counterEl = document.getElementById("lyricCounter");
      const viewEl = document.getElementById("lyricView");
      const editorEl = document.getElementById("lyricEditor");
      const editWrapEl = document.getElementById("lyricEditWrap");
      const prevBtn = document.getElementById("lyricPrevBtn");
      const nextBtn = document.getElementById("lyricNextBtn");
      const editBtn = document.getElementById("lyricEditBtn");
      const saveBtn = document.getElementById("lyricSaveBtn");
      const cancelBtn = document.getElementById("lyricCancelBtn");
      let editing = false;
      viewEl.tabIndex = 0;
      viewEl.addEventListener("click", () => viewEl.focus());

      const renderStats = () => {
        const lines = [];
        lines.push(`单词 '${payload.word || ""}' 例句统计：`);
        lines.push(`• 总数量（查重前）：${originalTotal} 个`);
        lines.push(`• 总数量（查重后）：${allExamples.length} 个`);
        lines.push(`• 去重率：${dedupRate.toFixed(1)}%`);
        lines.push("");
        lines.push("各歌曲例句分布（查重前/后）：");
        if (!songStats.length) {
          lines.push("• 无有效例句来源");
        } else {
          for (const it of songStats) {
            lines.push(`• ${it.album} - ${it.title}：查重前 ${it.before} 个，查重后 ${it.after} 个`);
          }
        }
        statsEl.textContent = lines.join("\n");
      };

      const setEditMode = (flag) => {
        editing = Boolean(flag);
        editBtn.classList.toggle("hidden", editing);
        saveBtn.classList.toggle("hidden", !editing);
        cancelBtn.classList.toggle("hidden", !editing);
        viewEl.classList.toggle("hidden", editing);
        editWrapEl.classList.toggle("hidden", !editing);
        if (editing) {
          requestAnimationFrame(() => {
            editorEl.focus();
            editorEl.setSelectionRange(editorEl.value.length, editorEl.value.length);
          });
        }
      };

      const renderAt = () => {
        const current = allExamples[currentIndex];
        if (!current) return;
        titleEl.textContent = `当前歌曲：${current.title} - ${current.album}`;
        counterEl.textContent = `当前例句 ${currentIndex + 1}/${allExamples.length}（原始例句总数：${originalTotal}）`;
        viewEl.innerHTML = renderLyricWithFocus(current.lyric, payload.word, current.start, current.end);
        if (editing) editorEl.value = current.lyric || "";
        prevBtn.disabled = currentIndex <= 0;
        nextBtn.disabled = currentIndex >= allExamples.length - 1;

        const focus = viewEl.querySelector(".lyric-paragraph-focus");
        if (focus) {
          focus.scrollIntoView({ block: "center", inline: "nearest" });
        }
      };

      prevBtn.addEventListener("click", () => {
        if (currentIndex > 0) currentIndex -= 1;
        renderAt();
      });

      nextBtn.addEventListener("click", () => {
        if (currentIndex < allExamples.length - 1) currentIndex += 1;
        renderAt();
      });

      editBtn.addEventListener("click", () => {
        const current = allExamples[currentIndex];
        if (!current) return;
        editorEl.value = current.lyric || "";
        setEditMode(true);
      });

      cancelBtn.addEventListener("click", () => {
        setEditMode(false);
      });

      saveBtn.addEventListener("click", async () => {
        const current = allExamples[currentIndex];
        if (!current) return;
        try {
          const ret = await callApi("dictionary_update_lyric", current.title, current.album, editorEl.value || "");
          toast(ret?.message || "保存完成", ret?.ok ? "info" : "warn");
          if (ret?.ok) {
            await loadDictionaryExamples(payload.word);
            setEditMode(false);
            closeModal();
          }
        } catch (err) {
          toast(`保存失败：${err.message}`, "warn", 3200);
        }
      });

      renderStats();
      setEditMode(false);
      renderAt();
    });
  }

  function bindDictionaryEvents() {
    els.dictSearchBtn.addEventListener("click", () => runDictionarySearch());
    els.dictQuery.addEventListener("keydown", (e) => {
      if (e.key === "Enter") runDictionarySearch();
    });

    els.dictHistoryBtn.addEventListener("click", async () => {
      state.dictionary.historyVisible = !state.dictionary.historyVisible;
      if (state.dictionary.historyVisible && els.dictHistory.childElementCount === 0) {
        try {
          renderDictionaryHistory(await callApi("dictionary_history"));
        } catch (_) {
          renderDictionaryHistory([]);
        }
      }
      els.dictHistory.classList.toggle("hidden", !state.dictionary.historyVisible);
    });

    els.dictHistory.addEventListener("click", (e) => {
      const node = e.target.closest(".history-item[data-query]");
      if (!node) return;
      const query = node.dataset.query || "";
      els.dictQuery.value = query;
      state.dictionary.historyVisible = false;
      els.dictHistory.classList.add("hidden");
      runDictionarySearch(query);
    });

    els.dictResults.addEventListener("click", (e) => {
      const btn = e.target.closest(".dict-example-btn[data-word]");
      if (!btn) return;
      loadDictionaryExamples(btn.dataset.word || "");
    });

    els.dictExamples.addEventListener("click", (e) => {
      const btn = e.target.closest(".dict-context-btn[data-index]");
      if (!btn || !state.dictionary.currentExamplesPayload) return;
      const idx = Number(btn.dataset.index);
      if (!Number.isInteger(idx)) return;
      openLyricContext(state.dictionary.currentExamplesPayload, idx);
    });
  }

  function getEditorText() {
    return (els.writingEditor.innerText || "").replace(/\r/g, "");
  }

  async function restoreModuleSnapshot(appId, shouldRunSearch = false) {
    if (appId === "dictionary") {
      const snapshot = loadJson(STORAGE_KEYS.dictSnapshot, {});
      if (typeof snapshot.query === "string") els.dictQuery.value = snapshot.query;
      els.dictExact.checked = Boolean(snapshot.exact);
      if (shouldRunSearch && String(snapshot.query || "").trim()) {
        await runDictionarySearch(snapshot.query, Boolean(snapshot.exact));
      }
      return;
    }

    if (appId === "writing") {
      const snapshot = loadJson(STORAGE_KEYS.writingSnapshot, {});
      if (typeof snapshot.text === "string" && getEditorText() !== snapshot.text) {
        els.writingEditor.textContent = snapshot.text;
        state.writing.selectedSidebarKey = "";
        closeInfoPopup();
      }
      if (typeof snapshot.dictQuery === "string") els.writingDictQuery.value = snapshot.dictQuery;
      els.writingDictExact.checked = Boolean(snapshot.dictExact);
      if (shouldRunSearch) await runWritingCheck(true);
    }
  }

  function locateDomPointByTextOffset(root, targetOffset) {
    const total = getEditorText().length;
    const offset = clamp(targetOffset, 0, total);
    let consumed = 0;
    let found = null;

    const walk = (node) => {
      if (found) return;
      if (node.nodeType === Node.TEXT_NODE) {
        const text = node.nodeValue || "";
        const len = text.length;
        if (offset <= consumed + len) {
          found = { node, offset: offset - consumed };
          return;
        }
        consumed += len;
        return;
      }
      if (node.nodeType === Node.ELEMENT_NODE && node.tagName === "BR") {
        if (offset <= consumed + 1) {
          const parent = node.parentNode;
          const index = Array.prototype.indexOf.call(parent.childNodes, node);
          found = { node: parent, offset: index + 1 };
          return;
        }
        consumed += 1;
        return;
      }
      const children = node.childNodes || [];
      for (let i = 0; i < children.length; i += 1) walk(children[i]);
    };

    walk(root);
    if (found) return found;
    return { node: root, offset: root.childNodes.length };
  }

  function setCaretRangeByOffset(root, start, end = start) {
    const s = locateDomPointByTextOffset(root, start);
    const e = locateDomPointByTextOffset(root, end);
    const range = document.createRange();
    range.setStart(s.node, s.offset);
    range.setEnd(e.node, e.offset);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
  }

  function getCaretOffset(root) {
    const sel = window.getSelection();
    if (!sel || !sel.rangeCount) return 0;
    const range = sel.getRangeAt(0);
    const probe = range.cloneRange();
    probe.selectNodeContents(root);
    probe.setEnd(range.endContainer, range.endOffset);
    return probe.toString().length;
  }

  function offsetFromPoint(root, clientX, clientY) {
    let range = null;
    if (document.caretRangeFromPoint) {
      range = document.caretRangeFromPoint(clientX, clientY);
    } else if (document.caretPositionFromPoint) {
      const pos = document.caretPositionFromPoint(clientX, clientY);
      if (pos) {
        range = document.createRange();
        range.setStart(pos.offsetNode, pos.offset);
        range.collapse(true);
      }
    }
    if (!range) return getCaretOffset(root);
    const probe = document.createRange();
    probe.selectNodeContents(root);
    probe.setEnd(range.endContainer, range.endOffset);
    return probe.toString().length;
  }

  function buildHighlightTypeArray(text, unknownRanges, lowstatRanges) {
    const arr = new Array(text.length).fill(0);
    for (const [s0, e0] of lowstatRanges || []) {
      const s = clamp(Number(s0), 0, text.length);
      const e = clamp(Number(e0), s, text.length);
      for (let i = s; i < e; i += 1) arr[i] = Math.max(arr[i], 1);
    }
    for (const [s0, e0] of unknownRanges || []) {
      const s = clamp(Number(s0), 0, text.length);
      const e = clamp(Number(e0), s, text.length);
      for (let i = s; i < e; i += 1) arr[i] = 2;
    }
    return arr;
  }

  function renderColoredEditorHtml(text, unknownRanges, lowstatRanges) {
    const source = String(text || "");
    const types = buildHighlightTypeArray(source, unknownRanges, lowstatRanges);
    let html = "";
    let active = 0;
    const closeSpan = () => {
      if (active !== 0) html += "</span>";
      active = 0;
    };
    const openSpan = (t) => {
      if (t === 2) html += '<span class="mark-unknown" data-hl="unknown" style="color:#b00020;font-weight:700">';
      if (t === 1) html += '<span class="mark-lowstat" data-hl="lowstat" style="color:#0d4ba8;font-weight:700">';
      active = t;
    };

    for (let i = 0; i < source.length; i += 1) {
      const t = types[i];
      if (t !== active) {
        closeSpan();
        if (t !== 0) openSpan(t);
      }
      const ch = source[i];
      if (ch === "\n") {
        html += "<br>";
      } else {
        html += escapeHtml(ch);
      }
    }
    closeSpan();
    return html;
  }

  function renderWritingSidebar(items) {
    if (!Array.isArray(items) || items.length === 0) {
      els.writingSidebar.innerHTML = '<div class="sidebar-item">暂无高亮词。</div>';
      return;
    }
    els.writingSidebar.innerHTML = items
      .map((it, index) => {
        const reasons = (it.reasons || []).join("，");
        const active = state.writing.selectedSidebarKey === `${it.pos}|${it.display}` ? " active" : "";
        return `
          <div class="sidebar-item ${escapeHtml(it.type || "unknown")}${active}"
               data-index="${index}"
               data-pos="${Number(it.pos) || 0}"
               data-word="${escapeHtml(it.display || "")}"
               data-type="${escapeHtml(it.type || "unknown")}">
            <div>${escapeHtml(it.display || "")}</div>
            <div class="result-meta">${reasons ? escapeHtml(reasons) : "无附加说明"}</div>
            <div class="result-meta">count: ${Number(it.count) || 0} | variety: ${Number(it.variety) || 0}</div>
          </div>
        `;
      })
      .join("");
  }

  async function renderLookupToBottom(selectedText) {
    const text = String(selectedText || "").trim();
    if (!text) return;
    try {
      const ret = await callApi("writing_lookup", text);
      if (!ret?.ok) {
        els.writingExplanation.textContent = ret?.message || "未找到信息。";
        return;
      }
      const explanations = (ret.explanations || [])
        .map((it) => `<div class="result-item"><strong>${escapeHtml(it.word || "")}</strong>：${escapeHtml(it.explanation || "未找到释义")}</div>`)
        .join("");
      const similars = (ret.similar_words || [])
        .map((it) => `<div class="result-item">建议：${escapeHtml(it.word || "")} → ${escapeHtml(it.similar_word || "")}（相似度 ${it.score ?? 0}）<br>${escapeHtml(it.explanation || "")}</div>`)
        .join("");
      els.writingExplanation.innerHTML = `
        <div class="explanation-stack">
          <div class="result-section-title">释义与建议</div>
          ${explanations || '<div class="result-item">无释义信息</div>'}
          ${similars}
        </div>
      `;
    } catch (err) {
      els.writingExplanation.textContent = `查询失败：${err.message}`;
    }
  }

  function renderLowstatDetailsToBottom(item) {
    const reasons = Array.isArray(item?.reasons) && item.reasons.length ? item.reasons.join("，") : "无";
    els.writingExplanation.innerHTML = `
      <div class="explanation-stack">
        <div class="result-section-title">高亮原因与数值</div>
        <div class="result-item"><strong>单词：</strong>${escapeHtml(item?.display || "")}</div>
        <div class="result-item"><strong>类型：</strong>${item?.type === "lowstat" ? "蓝色低词频词" : "红色未知词"}</div>
        <div class="result-item"><strong>词频：</strong>${Number(item?.count) || 0}</div>
        <div class="result-item"><strong>泛度：</strong>${Number(item?.variety) || 0}</div>
        <div class="result-item"><strong>count：</strong>${Number(item?.count) || 0}</div>
        <div class="result-item"><strong>variety：</strong>${Number(item?.variety) || 0}</div>
        <div class="result-item"><strong>原因：</strong>${escapeHtml(reasons)}</div>
      </div>
    `;
  }

  function closeInfoPopup() {
    if (!state.writing.infoPopup) return;
    state.writing.infoPopup.remove();
    state.writing.infoPopup = null;
  }

  function showInfoPopup(item, clientX, clientY) {
    closeInfoPopup();
    const popup = document.createElement("div");
    popup.className = "info-popup";
    const reasons = Array.isArray(item.reasons) && item.reasons.length ? item.reasons.join("，") : "无";
    popup.innerHTML = `
      <div class="info-popup-title">${escapeHtml(item.display || "")}</div>
      <div>类型：${item.type === "lowstat" ? "蓝色低词频词" : "红色未知词"}</div>
      <div>词频：${Number(item.count) || 0}</div>
      <div>泛度：${Number(item.variety) || 0}</div>
      <div>原因：${escapeHtml(reasons)}</div>
    `;
    popup.style.left = `${clientX + 8}px`;
    popup.style.top = `${clientY + 8}px`;
    document.body.appendChild(popup);
    state.writing.infoPopup = popup;
  }

  function findSidebarItemAtOffset(offset) {
    const items = state.writing.lastResult?.sidebar_items || [];
    if (!items.length) return null;
    const exact = items.find((it) => {
      const s = Number(it.pos) || 0;
      const e = s + String(it.display || "").length;
      return offset >= s && offset < e;
    });
    if (exact) return exact;
    let nearest = null;
    let best = Number.POSITIVE_INFINITY;
    for (const it of items) {
      const d = Math.abs((Number(it.pos) || 0) - offset);
      if (d < best) {
        best = d;
        nearest = it;
      }
    }
    return best <= 2 ? nearest : null;
  }

  async function runWritingCheck(immediate = false) {
    const perform = async () => {
      if (state.writing.isComposing) return;
      const text = getEditorText();
      const seq = ++state.writing.checkSeq;
      try {
        const ret = await callApi("writing_check_text", text);
        if (seq !== state.writing.checkSeq || state.writing.isComposing) return;
        state.writing.appliedSeq = seq;
        state.writing.lastResult = ret;
        const caret = getCaretOffset(els.writingEditor);
        els.writingEditor.innerHTML = renderColoredEditorHtml(text, ret.unknown_ranges || [], ret.lowstat_ranges || []);
        setCaretRangeByOffset(els.writingEditor, clamp(caret, 0, getEditorText().length));
        renderWritingSidebar(ret.sidebar_items || []);
        els.writingStatus.textContent = ret.status || "";
      } catch (err) {
        if (seq !== state.writing.checkSeq) return;
        toast(`检查失败：${err.message}`, "warn", 3200);
      }
    };

    if (immediate) {
      clearTimeout(state.writing.debounceTimer);
      await perform();
      return;
    }

    clearTimeout(state.writing.debounceTimer);
    state.writing.debounceTimer = setTimeout(() => {
      perform();
    }, 280);
  }

  function applyWritingSettings(settings) {
    state.writing.settings = settings || state.writing.settings;
    els.settingsStrictCase.checked = Boolean(state.writing.settings.strict_case);
    els.settingsUndo.value = Number(state.writing.settings.max_undo_steps) || 100;
    renderExcludedWords(state.writing.settings.excluded_words || []);
  }

  function applyAppSettings(settings) {
    state.settings.autoUpdate = Boolean(settings?.auto_update);
    state.settings.status = String(settings?.auto_update_status || "");
    if (els.autoUpdateToggle) els.autoUpdateToggle.checked = state.settings.autoUpdate;
    if (els.autoUpdateStatus) els.autoUpdateStatus.textContent = state.settings.status;
  }

  function renderExcludedWords(words) {
    const source = Array.isArray(words) ? words : [];
    const normalized = [];
    const seen = new Set();
    for (const raw of source) {
      const word = String(raw || "").trim();
      if (!word || seen.has(word)) continue;
      seen.add(word);
      normalized.push(word);
    }
    state.writing.settings.excluded_words = normalized;
    if (!normalized.length) {
      els.excludedList.innerHTML = '<span class="result-meta">暂无排除词</span>';
      return;
    }
    els.excludedList.innerHTML = normalized
      .map((w) => `
        <span class="excluded-tag" data-word="${escapeHtml(w)}">
          ${escapeHtml(w)}
          <button class="ghost small excluded-del" type="button" data-word="${escapeHtml(w)}">删除</button>
        </span>
      `).join("");
  }

  function centerEditorSelection() {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;
    const range = sel.getRangeAt(0).cloneRange();
    const editor = els.writingEditor;
    const editorRect = editor.getBoundingClientRect();
    let rect = range.getBoundingClientRect();
    if ((!rect || rect.height === 0) && range.getClientRects().length > 0) rect = range.getClientRects()[0];
    let targetCenterY = null;
    if (rect && rect.height > 0) {
      targetCenterY = rect.top - editorRect.top + editor.scrollTop + rect.height / 2;
    } else {
      const startNode = range.startContainer?.nodeType === Node.TEXT_NODE
        ? range.startContainer.parentElement
        : range.startContainer;
      if (startNode && editor.contains(startNode)) {
        const nr = startNode.getBoundingClientRect();
        targetCenterY = nr.top - editorRect.top + editor.scrollTop + nr.height / 2;
      }
    }
    if (targetCenterY == null) return;
    const nextTop = Math.max(0, targetCenterY - editor.clientHeight / 2);
    editor.scrollTop = nextTop;
  }

  function syncSidebarActiveClasses() {
    const key = state.writing.selectedSidebarKey;
    const nodes = els.writingSidebar.querySelectorAll(".sidebar-item[data-pos][data-word]");
    nodes.forEach((node) => {
      const nodeKey = `${node.dataset.pos || "0"}|${node.dataset.word || ""}`;
      node.classList.toggle("active", key !== "" && nodeKey === key);
    });
  }

  function activateSidebarWord(item) {
    if (!item) return;
    state.writing.selectedSidebarKey = `${item.pos}|${item.display}`;
    syncSidebarActiveClasses();
  }

  function selectSidebarWord(item) {
    if (!item) return;
    const start = Number(item.pos) || 0;
    const len = String(item.display || "").length;
    const end = start + len;
    const maxLen = getEditorText().length;
    activateSidebarWord(item);
    els.writingEditor.focus();
    setCaretRangeByOffset(els.writingEditor, clamp(start, 0, maxLen), clamp(end, 0, maxLen));
    requestAnimationFrame(() => requestAnimationFrame(() => centerEditorSelection()));
  }

  function bindWritingEvents() {
    els.writingEditor.addEventListener("compositionstart", () => {
      state.writing.isComposing = true;
      state.writing.checkSeq += 1;
      clearTimeout(state.writing.debounceTimer);
    });

    els.writingEditor.addEventListener("compositionend", () => {
      state.writing.isComposing = false;
      closeInfoPopup();
      saveModuleSnapshot("writing");
      runWritingCheck(false);
    });

    els.writingEditor.addEventListener("input", (e) => {
      closeInfoPopup();
      if (state.writing.isComposing || e.isComposing) return;
      saveModuleSnapshot("writing");
      runWritingCheck(false);
    });

    els.writingEditor.addEventListener("contextmenu", async (e) => {
      const selected = String(window.getSelection()?.toString() || "").trim();
      if (selected) {
        e.preventDefault();
        closeInfoPopup();
        await renderLookupToBottom(selected);
        return;
      }

      const offset = offsetFromPoint(els.writingEditor, e.clientX, e.clientY);
      const item = findSidebarItemAtOffset(offset);
      if (!item) {
        closeInfoPopup();
        return;
      }
      if (item.type === "lowstat" || item.type === "unknown") {
        e.preventDefault();
        showInfoPopup(item, e.clientX, e.clientY);
      }
    });

    document.addEventListener("mousedown", (e) => {
      if (!state.writing.infoPopup) return;
      if (state.writing.infoPopup.contains(e.target)) return;
      closeInfoPopup();
    });

    els.writingSidebar.addEventListener("click", (e) => {
      const node = e.target.closest(".sidebar-item[data-index]");
      if (!node) return;
      const index = Number(node.dataset.index);
      const item = state.writing.lastResult?.sidebar_items?.[index];
      activateSidebarWord(item);
    });

    els.writingSidebar.addEventListener("dblclick", (e) => {
      const node = e.target.closest(".sidebar-item[data-index]");
      if (!node) return;
      const index = Number(node.dataset.index);
      const item = state.writing.lastResult?.sidebar_items?.[index];
      if (!item) return;
      selectSidebarWord(item);
      if (item.type === "lowstat") {
        renderLowstatDetailsToBottom(item);
      } else {
        renderLookupToBottom(item.display);
      }
    });

    els.writingImportBtn.addEventListener("click", () => {
      els.fileLoader.value = "";
      els.fileLoader.click();
    });

    els.fileLoader.addEventListener("change", async () => {
      const file = els.fileLoader.files?.[0];
      if (!file) return;
      const text = await file.text();
      els.writingEditor.textContent = text;
      state.writing.selectedSidebarKey = "";
      closeInfoPopup();
      saveModuleSnapshot("writing");
      if (getEditorText().trim()) {
        await runWritingCheck(true);
      }
      toast(`已导入：${file.name}`);
    });

    els.writingExportBtn.addEventListener("click", async () => {
      try {
        const ret = await callApi("writing_export_text", getEditorText(), "writing_assistant.txt");
        toast(ret?.message || "导出完成", ret?.ok ? "info" : "warn", 3200);
      } catch (err) {
        toast(`导出失败：${err.message}`, "warn", 3200);
      }
    });

    els.writingSettingsBtn.addEventListener("click", async () => {
      els.writingSettingsPanel.classList.toggle("hidden");
      if (els.writingSettingsPanel.classList.contains("hidden")) return;
      try {
        const latest = await callApi("writing_get_settings");
        applyWritingSettings(latest || state.writing.settings);
      } catch (_) {
        renderExcludedWords(state.writing.settings.excluded_words || []);
      }
    });

    els.settingsCloseBtn.addEventListener("click", () => {
      els.writingSettingsPanel.classList.add("hidden");
    });

    els.excludedAddBtn.addEventListener("click", () => {
      const value = String(els.excludedInput.value || "").trim();
      if (!value) return;
      const current = new Set(state.writing.settings.excluded_words || []);
      current.add(value);
      renderExcludedWords(Array.from(current));
      els.excludedInput.value = "";
    });

    els.excludedList.addEventListener("click", (e) => {
      const btn = e.target.closest(".excluded-del[data-word]");
      if (!btn) return;
      const word = btn.dataset.word || "";
      renderExcludedWords((state.writing.settings.excluded_words || []).filter((w) => w !== word));
    });

    els.settingsSaveBtn.addEventListener("click", async () => {
      const payload = {
        strict_case: Boolean(els.settingsStrictCase.checked),
        max_undo_steps: Number(els.settingsUndo.value) || 100,
        excluded_words: state.writing.settings.excluded_words || [],
      };
      try {
        const ret = await callApi("writing_save_settings", payload);
        if (ret?.ok) {
          applyWritingSettings(ret.settings || payload);
          els.writingStatus.textContent = ret.status || "";
          els.writingSettingsPanel.classList.add("hidden");
          await runWritingCheck(true);
        }
        toast(ret?.message || "设置已保存", ret?.ok ? "info" : "warn");
      } catch (err) {
        toast(`保存设置失败：${err.message}`, "warn", 3200);
      }
    });

    els.writingDictSearchBtn.addEventListener("click", async () => {
      const query = String(els.writingDictQuery.value || "").trim();
      if (!query) return;
      saveModuleSnapshot("writing");
      if (state.isNativeDetached) {
        saveJson(STORAGE_KEYS.dictSnapshot, { query, exact: Boolean(els.writingDictExact.checked) });
        try {
          await callApi("detach_native_window", "dictionary", Math.round(window.screenX + 60), Math.round(window.screenY + 60));
        } catch (err) {
          toast(`打开词典窗口失败：${err.message}`, "warn", 3200);
        }
        return;
      }
      state.activeDocked = "dictionary";
      renderDockPanels();
      updateTabVisualState();
      els.dictQuery.value = query;
      els.dictExact.checked = Boolean(els.writingDictExact.checked);
      await runDictionarySearch(query, els.writingDictExact.checked);
    });
  }

  function bindAppSettingsEvents() {
    if (!els.autoUpdateToggle) return;
    els.autoUpdateToggle.addEventListener("change", async () => {
      const nextValue = Boolean(els.autoUpdateToggle.checked);
      try {
        const ret = await callApi("app_save_settings", { auto_update: nextValue });
        applyAppSettings(ret?.settings || { auto_update: nextValue });
        toast(ret?.message || "设置已保存。", ret?.ok ? "info" : "warn");
      } catch (err) {
        els.autoUpdateToggle.checked = state.settings.autoUpdate;
        toast(`保存设置失败：${err.message}`, "warn", 3200);
      }
    });
  }

  function renderDbmanagerTableList() {
    const list = els.dbmTableList;
    if (!list) return;
    list.innerHTML = state.dbmanager.tables.map((t) => {
      const cls = t === state.dbmanager.currentTable ? "table-item active" : "table-item";
      return `<div class="${cls}" data-table="${escapeHtml(t)}">${escapeHtml(t)}</div>`;
    }).join("");

    list.querySelectorAll(".table-item").forEach((el) => {
      el.addEventListener("click", () => {
        loadDbmanagerTable(el.dataset.table);
      });
    });
  }

  async function loadDbmanagerTable(tableName) {
    state.dbmanager.currentTable = tableName;
    state.dbmanager.selectedIds = new Set();
    renderDbmanagerTableList();
    try {
      const ret = await callApi("dbmanager_get_all_data", tableName);
      if (ret?.ok) {
        state.dbmanager.fields = ret.fields || [];
        state.dbmanager.data = ret.data || [];
      } else {
        state.dbmanager.fields = [];
        state.dbmanager.data = [];
        toast(ret?.message || "加载失败", "warn");
      }
    } catch (err) {
      state.dbmanager.fields = [];
      state.dbmanager.data = [];
      toast(`加载数据失败：${err.message}`, "warn");
    }
    renderDbmanagerData();
  }

  function renderDbmanagerData() {
    const fields = state.dbmanager.fields;
    const data = state.dbmanager.data;
    const wrap = els.dbmDataTable;
    if (!wrap) return;

    if (!fields.length) {
      wrap.innerHTML = '<div style="padding:20px;color:var(--muted)">请左侧选择数据表</div>';
      els.dbmStatus.textContent = "";
      return;
    }

    let html = '<table class="data-table"><thead><tr>';
    html += '<th style="width:40px"><input type="checkbox" id="dbmSelectAll" /></th>';
    for (const f of fields) {
      html += `<th>${escapeHtml(f)}</th>`;
    }
    html += '</tr></thead><tbody>';

    for (const row of data) {
      const rowId = row.id != null ? String(row.id) : "";
      const selected = rowId && state.dbmanager.selectedIds.has(rowId);
      html += `<tr class="${selected ? 'selected' : ''}" data-row-id="${escapeHtml(rowId)}">`;
      html += `<td><input type="checkbox" ${selected ? 'checked' : ''} /></td>`;
      for (const f of fields) {
        html += `<td title="${escapeHtml(String(row[f] ?? ''))}">${escapeHtml(String(row[f] ?? ''))}</td>`;
      }
      html += '</tr>';
    }
    html += '</tbody></table>';
    wrap.innerHTML = html;
    els.dbmStatus.textContent = `共 ${data.length} 条记录`;

    const selectAllCb = wrap.querySelector("#dbmSelectAll");
    const rowCbs = wrap.querySelectorAll("tbody input[type=checkbox]");
    if (selectAllCb) {
      selectAllCb.checked = rowCbs.length > 0 && [...rowCbs].every((cb) => cb.checked);
      selectAllCb.addEventListener("change", () => {
        const check = selectAllCb.checked;
        rowCbs.forEach((cb) => {
          cb.checked = check;
          const rid = cb.closest("tr")?.dataset.rowId;
          if (rid) {
            if (check) state.dbmanager.selectedIds.add(rid);
            else state.dbmanager.selectedIds.delete(rid);
          }
        });
        syncDbmanagerRowSelection();
      });
    }

    rowCbs.forEach((cb) => {
      cb.addEventListener("change", () => {
        const rid = cb.closest("tr")?.dataset.rowId;
        if (rid) {
          if (cb.checked) state.dbmanager.selectedIds.add(rid);
          else state.dbmanager.selectedIds.delete(rid);
        }
        syncDbmanagerRowSelection();
      });
    });
  }

  function syncDbmanagerRowSelection() {
    const rows = els.dbmDataTable?.querySelectorAll("tbody tr");
    if (!rows) return;
    rows.forEach((tr) => {
      const cb = tr.querySelector("input[type=checkbox]");
      if (cb) tr.classList.toggle("selected", cb.checked);
    });
    const selectAllCb = els.dbmDataTable?.querySelector("#dbmSelectAll");
    const rowCbs = els.dbmDataTable?.querySelectorAll("tbody input[type=checkbox]");
    if (selectAllCb) {
      selectAllCb.checked = rowCbs && rowCbs.length > 0 && [...rowCbs].every((c) => c.checked);
    }
  }

  function getDbmanagerSelectedIds() {
    return [...state.dbmanager.selectedIds].map(Number).filter((n) => !isNaN(n));
  }

  function showDbmanagerDialog(title, fields, values, onSave) {
    const existing = document.querySelector(".dialog-overlay");
    if (existing) existing.remove();

    const overlay = document.createElement("div");
    overlay.className = "dialog-overlay";
    let fieldsHtml = "";
    for (const f of fields) {
      if (f === "id") continue;
      const label = f;
      const val = escapeHtml(values[f] || "");
      const isLong = (values[f] && values[f].length > 40) || f === "explanation" || f === "lyric";
      const inputHtml = isLong
        ? `<textarea id="dialog-f-${escapeHtml(f)}" rows="4">${val}</textarea>`
        : `<input id="dialog-f-${escapeHtml(f)}" type="text" value="${val}" />`;
      fieldsHtml += `<div class="dialog-field"><label>${escapeHtml(label)}</label>${inputHtml}</div>`;
    }

    overlay.innerHTML = `
      <div class="dialog-card">
        <div class="dialog-head"><h3>${escapeHtml(title)}</h3><button class="close-btn dialog-close-btn">&#x2715;</button></div>
        <div class="dialog-body">${fieldsHtml}</div>
        <div class="dialog-actions">
          <button class="ghost dialog-cancel-btn">取消</button>
          <button class="dialog-save-btn">保存</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);

    const close = () => overlay.remove();
    overlay.querySelector(".dialog-close-btn").addEventListener("click", close);
    overlay.querySelector(".dialog-cancel-btn").addEventListener("click", close);
    overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });

    overlay.querySelector(".dialog-save-btn").addEventListener("click", () => {
      const result = {};
      for (const f of fields) {
        if (f === "id") continue;
        const el = overlay.querySelector(`#dialog-f-${CSS.escape(f)}`);
        result[f] = el ? el.value : "";
      }
      onSave(result, close);
    });

    overlay.addEventListener("keydown", (e) => {
      if (e.key === "Escape") close();
    });
  }

  async function dbmanagerRefresh() {
    if (!state.dbmanager.currentTable) {
      toast("请先选择数据表", "warn");
      return;
    }
    await loadDbmanagerTable(state.dbmanager.currentTable);
    toast("已刷新", "info");
  }

  async function dbmanagerAddRecord() {
    const table = state.dbmanager.currentTable;
    if (!table) { toast("请先选择数据表", "warn"); return; }
    const fields = state.dbmanager.fields;
    showDbmanagerDialog("新增记录 - " + table, fields, {}, async (values, close) => {
      try {
        const ret = await callApi("dbmanager_add_record", table, values);
        toast(ret?.message || "", ret?.ok ? "info" : "warn");
        if (ret?.ok) { close(); await loadDbmanagerTable(table); }
      } catch (err) { toast(`新增失败：${err.message}`, "warn"); }
    });
  }

  async function dbmanagerEditRecord() {
    const ids = getDbmanagerSelectedIds();
    if (ids.length !== 1) { toast("请选择一条记录", "warn"); return; }
    const table = state.dbmanager.currentTable;
    const record = state.dbmanager.data.find((r) => String(r.id) === String(ids[0]));
    if (!record) { toast("未找到该记录", "warn"); return; }
    const fields = state.dbmanager.fields;
    showDbmanagerDialog("修改记录 - " + table, fields, record, async (values, close) => {
      try {
        const ret = await callApi("dbmanager_update_record", table, ids[0], values);
        toast(ret?.message || "", ret?.ok ? "info" : "warn");
        if (ret?.ok) { close(); await loadDbmanagerTable(table); }
      } catch (err) { toast(`修改失败：${err.message}`, "warn"); }
    });
  }

  async function dbmanagerDeleteRecords() {
    const ids = getDbmanagerSelectedIds();
    if (!ids.length) { toast("请选择要删除的记录", "warn"); return; }
    if (!confirm(`确认删除 ${ids.length} 条记录吗？此操作不可撤销。`)) return;
    const table = state.dbmanager.currentTable;
    try {
      const ret = await callApi("dbmanager_delete_records", table, ids);
      toast(ret?.message || "", ret?.ok ? "info" : "warn");
      if (ret?.ok) await loadDbmanagerTable(table);
    } catch (err) { toast(`删除失败：${err.message}`, "warn"); }
  }

  async function dbmanagerSearch() {
    const table = state.dbmanager.currentTable;
    if (!table) { toast("请先选择数据表", "warn"); return; }
    const kw = (els.dbmSearchInput?.value || "").trim();
    try {
      const ret = await callApi("dbmanager_search", table, kw);
      if (ret?.ok) {
        state.dbmanager.data = ret.data || [];
        state.dbmanager.selectedIds = new Set();
        renderDbmanagerData();
        els.dbmStatus.textContent = kw ? `搜索 "${kw}" — ${ret.data.length} 条结果` : `共 ${ret.data.length} 条记录`;
      } else {
        toast(ret?.message || "搜索失败", "warn");
      }
    } catch (err) { toast(`搜索失败：${err.message}`, "warn"); }
  }

  async function dbmanagerShowAll() {
    const table = state.dbmanager.currentTable;
    if (!table) return;
    els.dbmSearchInput.value = "";
    await loadDbmanagerTable(table);
  }

  function renderGlobalResults() {
    const results = state.dbmanager.globalResults;
    if (!results || !results.length) {
      els.dbmGlobalStatus.textContent = "无结果";
      return;
    }
    els.dbmGlobalStatus.textContent = `找到 ${results.length} 条结果`;

    let html = '<table class="global-results-table"><thead><tr>';
    html += '<th><input type="checkbox" id="dbmGlobalSelectAll" /></th>';
    html += '<th>表</th><th>ID</th><th>字段</th><th>值</th>';
    html += '</tr></thead><tbody>';
    for (let i = 0; i < results.length; i++) {
      const r = results[i];
      html += `<tr data-gidx="${i}">`;
      html += `<td><input type="checkbox" /></td>`;
      html += `<td>${escapeHtml(r.table || "")}</td>`;
      html += `<td>${escapeHtml(String(r.id ?? ""))}</td>`;
      html += `<td>${escapeHtml(r.field || "")}</td>`;
      html += `<td>${escapeHtml(String(r.value ?? ""))}</td>`;
      html += '</tr>';
    }
    html += '</tbody></table>';

    let container = document.getElementById("dbmGlobalResults");
    if (!container) {
      container = document.createElement("div");
      container.id = "dbmGlobalResults";
      container.className = "global-results card";
      container.style.cssText = "max-height:220px;overflow:auto;margin-top:8px;padding:8px";
      els.dbmGlobalStatus.parentElement.after(container);
    }
    container.innerHTML = html;

    const selectAllCb = container.querySelector("#dbmGlobalSelectAll");
    const rowCbs = container.querySelectorAll("tbody input[type=checkbox]");
    if (selectAllCb) {
      selectAllCb.addEventListener("change", () => {
        rowCbs.forEach((cb, i) => { cb.checked = selectAllCb.checked; });
      });
    }
  }

  async function dbmanagerGlobalSearch() {
    const kw = (els.dbmGlobalSearchInput?.value || "").trim();
    if (!kw) { toast("请输入搜索关键词", "warn"); return; }
    try {
      const ret = await callApi("dbmanager_global_search", kw);
      if (ret?.ok) {
        state.dbmanager.globalResults = ret.results || [];
        renderGlobalResults();
      }
    } catch (err) { toast(`全局搜索失败：${err.message}`, "warn"); }
  }

  async function dbmanagerGlobalReplace() {
    const kw = (els.dbmGlobalSearchInput?.value || "").trim();
    const rep = (els.dbmReplaceInput?.value || "").trim();
    if (!kw) { toast("请输入查找关键词", "warn"); return; }
    if (!rep) { toast("请输入替换内容", "warn"); return; }

    const container = document.getElementById("dbmGlobalResults");
    const rowCbs = container?.querySelectorAll("tbody input[type=checkbox]");
    if (!rowCbs || !rowCbs.length) { toast("请先执行全局搜索", "warn"); return; }

    const matchRecords = [];
    rowCbs.forEach((cb) => {
      if (cb.checked) {
        const tr = cb.closest("tr");
        const idx = parseInt(tr?.dataset.gidx);
        if (!isNaN(idx) && state.dbmanager.globalResults[idx]) {
          matchRecords.push(state.dbmanager.globalResults[idx]);
        }
      }
    });

    if (!matchRecords.length) { toast("请勾选要替换的记录", "warn"); return; }
    if (!confirm(`确认将 ${matchRecords.length} 处 "${kw}" 替换为 "${rep}" 吗？此操作不可撤销。`)) return;

    try {
      const ret = await callApi("dbmanager_global_replace", kw, rep, matchRecords);
      toast(ret?.message || `已替换 ${ret?.replaced_count || 0} 处`, ret?.ok ? "info" : "warn");
      if (ret?.ok) {
        await dbmanagerGlobalSearch();
        if (state.dbmanager.currentTable) await loadDbmanagerTable(state.dbmanager.currentTable);
      }
    } catch (err) { toast(`替换失败：${err.message}`, "warn"); }
  }

  async function dbmanagerLoadTables() {
    try {
      state.dbmanager.tables = await callApi("dbmanager_get_tables");
      if (state.dbmanager.tables.length && !state.dbmanager.currentTable) {
        state.dbmanager.currentTable = state.dbmanager.tables[0];
      }
      renderDbmanagerTableList();
      if (state.dbmanager.currentTable) {
        await loadDbmanagerTable(state.dbmanager.currentTable);
      }
    } catch (err) {
      toast(`加载表列表失败：${err.message}`, "warn");
    }
  }

  function bindDbmanagerEvents() {
    if (!els.dbmRefreshBtn) return;
    els.dbmRefreshBtn.addEventListener("click", dbmanagerRefresh);
    els.dbmSearchBtn.addEventListener("click", dbmanagerSearch);
    els.dbmShowAllBtn.addEventListener("click", dbmanagerShowAll);
    els.dbmAddBtn.addEventListener("click", dbmanagerAddRecord);
    els.dbmEditBtn.addEventListener("click", dbmanagerEditRecord);
    els.dbmDeleteBtn.addEventListener("click", dbmanagerDeleteRecords);
    els.dbmGlobalSearchBtn.addEventListener("click", dbmanagerGlobalSearch);
    els.dbmReplaceBtn.addEventListener("click", dbmanagerGlobalReplace);

    els.dbmSearchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") dbmanagerSearch();
    });
    els.dbmGlobalSearchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") dbmanagerGlobalSearch();
    });
  }

  async function bootstrap() {
    try {
      const ret = await callApi("bootstrap");
      applyWritingSettings(ret?.writing_settings || state.writing.settings);
      applyAppSettings(ret?.app_settings || state.settings);
      els.writingStatus.textContent = ret?.writing_status || "";
      renderDictionaryHistory(ret?.dictionary_history || []);

      if (!state.isNativeDetached) {
        const initial = ret?.initial_tab === "writing" ? "writing" : "dictionary";
        activateDocked(initial);
      } else {
        renderDockPanels();
        await restoreModuleSnapshot(state.nativeAppId, state.nativeAppId === "dictionary");
      }
      if (ret?.startup_query) {
        els.dictQuery.value = ret.startup_query;
        els.dictExact.checked = Boolean(ret.startup_exact);
        await runDictionarySearch(ret.startup_query, ret.startup_exact);
      }
      await runWritingCheck(true);
      dbmanagerLoadTables();
    } catch (err) {
      toast(`初始化失败：${err.message}`, "warn", 3600);
    }
  }

  function bindGlobal() {
    els.modalCloseBtn.addEventListener("click", closeModal);
    els.modalRoot.addEventListener("click", (e) => {
      if (e.target === els.modalRoot) closeModal();
    });

    window.addEventListener("storage", (e) => {
      if (state.isNativeDetached) return;
      if (e.key === STORAGE_KEYS.writingSnapshot && state.apps.writing.detached) {
        restoreModuleSnapshot("writing", false);
      }
    });
  }

  function init() {
    bindBaseElements();
    configureWindowMode();
    bindGlobal();
    bindTabs();
    bindSplitters();
    bindDictionaryEvents();
    bindWritingEvents();
    bindAppSettingsEvents();
    bindDbmanagerEvents();
    renderDockPanels();
    updateTabVisualState();
    bootstrap();
  }

  if (document.readyState === "loading") {
    window.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
