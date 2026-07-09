function bindBaseElements() {
  var ids = [
    "tabBar", "workspace", "dockHost", "floatingLayer",
    "modalRoot", "modalTitle", "modalBody", "modalCloseBtn", "toastRoot",
    "dictLayout", "dictSplit", "dictQuery", "dictExact", "dictSearchBtn",
    "dictHistoryBtn", "dictHistory", "dictResults", "dictExamples",
    "writingWorkspace", "writingTop", "writingMainSplit", "writingBottomSplit",
    "writingEditor", "writingSidebar", "writingStatus", "writingExplanation",
    "writingImportBtn", "writingExportBtn", "writingSettingsBtn", "writingSettingsPanel",
    "writingDictQuery", "writingDictExact", "writingDictSearchBtn",
    "settingsStrictCase", "settingsUndo", "settingsDictionaryFormat", "settingsDictionarySeparators",
    "excludedInput", "excludedAddBtn",
    "excludedList", "settingsSaveBtn", "settingsCloseBtn",
    "translatorDirection", "translatorSwapBtn", "translatorTranslateBtn",
    "translatorInput", "translatorOutput", "translatorSplit", "translatorDetails", "translatorStatus",
    "autoUpdateToggle", "alicFontToggle", "alicHoverToggle", "alicHoverDelaySlider", "alicHoverDelayLabel",
    "checkUpdateBtn", "updateCheckStatus", "forceDownloadBtn",
    "dbmTableList", "dbmRefreshBtn", "dbmSearchInput", "dbmSearchBtn",
    "dbmShowAllBtn", "dbmAddBtn", "dbmDeleteBtn",
    "dbmDiscardBtn", "dbmCommitBtn",
    "dbmUpdateWordCountBtn", "dbmClassifyWordsBtn", "dbmExportCsvBtn", "dbmExportDbBtn",
    "dbmDataTable", "dbmStatus", "dbmGlobalSearchInput",
    "dbmGlobalSearchBtn", "dbmGlobalSelectAllBtn", "dbmReplaceInput", "dbmReplaceBtn", "dbmGlobalStatus",
    "fileLoader",
  ];
  for (var i = 0; i < ids.length; i++) els[ids[i]] = document.getElementById(ids[i]);
}

function configureWindowMode() {
  if (!state.isNativeDetached) return;
  document.body.classList.add("native-detached-window");
  state.activeDocked = state.nativeAppId;
  for (var i = 0; i < APP_IDS.length; i++) {
    var appId = APP_IDS[i];
    if (appId !== state.nativeAppId) state.apps[appId].detached = true;
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
  return els.tabBar.querySelector('.tab-item[data-app="' + appId + '"]');
}

function getAppPanel(appId) {
  return document.getElementById("panel-" + appId);
}

function renderDockPanels() {
  if (state.isNativeDetached) {
    for (var i = 0; i < APP_IDS.length; i++) {
      var p = getAppPanel(APP_IDS[i]);
      p.classList.toggle("show", APP_IDS[i] === state.nativeAppId);
    }
    return;
  }
  for (var i = 0; i < APP_IDS.length; i++) {
    var a = APP_IDS[i];
    var panel = getAppPanel(a);
    panel.classList.toggle("show", !state.apps[a].detached && state.activeDocked === a);
  }
}

function updateTabVisualState() {
  if (state.isNativeDetached) return;
  for (var i = 0; i < APP_IDS.length; i++) {
    var a = APP_IDS[i];
    var tab = getTabButton(a);
    tab.classList.toggle("detached", state.apps[a].detached);
    tab.classList.toggle("active", !state.apps[a].detached && state.activeDocked === a);
  }
}

function activateDocked(appId) {
  if (state.isNativeDetached) return;
  if (state.apps[appId].detached) {
    var win = state.apps[appId].floatingWindow;
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
  for (var i = 0; i < APP_IDS.length; i++) {
    if (APP_IDS[i] !== exceptAppId && !state.apps[APP_IDS[i]].detached) return APP_IDS[i];
  }
  return null;
}

function saveModuleSnapshot(appId) {
  if (appId === "dictionary") {
    saveJson(STORAGE_KEYS.dictSnapshot, {
      query: els.dictQuery?.value || "", exact: Boolean(els.dictExact?.checked),
    });
    return;
  }
  if (appId === "writing") {
    saveJson(STORAGE_KEYS.writingSnapshot, {
      text: getEditorText(),
      dictQuery: els.writingDictQuery?.value || "",
      dictExact: Boolean(els.writingDictExact?.checked),
    });
    return;
  }
  if (appId === "translator") {
    saveJson(STORAGE_KEYS.translatorSnapshot, {
      direction: els.translatorDirection?.value || "zh_to_alician",
      input: els.translatorInput?.value || "",
      output: els.translatorOutput?.value || "",
      result: state.translator.lastResult || null,
    });
  }
}

async function detachAppToNativeWindow(appId, event) {
  if (state.isNativeDetached || DETACHABLE_APP_IDS.indexOf(appId) < 0 || state.apps[appId]?.detached) return;
  saveModuleSnapshot(appId);
  try {
    var ret = await callApi("detach_native_window", appId,
      Math.round(event.screenX), Math.round(event.screenY));
    toast(ret?.message || "已打开独立窗口。", ret?.ok ? "info" : "warn");
    if (!ret?.ok) return;
    state.apps[appId].detached = true;
    state.apps[appId].floatingWindow = null;
    if (state.activeDocked === appId) state.activeDocked = chooseNextDockedApp(appId) || appId;
    renderDockPanels();
    updateTabVisualState();
  } catch (err) { toast("打开独立窗口失败：" + err.message, "warn", 3200); }
}

window.__nativeAppReturned = function (appId) {
  if (APP_IDS.indexOf(appId) < 0) return;
  state.apps[appId].detached = false;
  state.apps[appId].floatingWindow = null;
  state.activeDocked = appId;
  renderDockPanels();
  updateTabVisualState();
  restoreModuleSnapshot(appId, true);
};

function bindFloatingDragging(win, head, appId) {
  var dragging = false, dx = 0, dy = 0;
  head.addEventListener("mousedown", function (e) {
    if (e.target.tagName === "BUTTON") return;
    dragging = true;
    bringFloatingToFront(win);
    var rect = win.getBoundingClientRect();
    dx = e.clientX - rect.left;
    dy = e.clientY - rect.top;
    e.preventDefault();
  });
  window.addEventListener("mousemove", function (e) {
    if (!dragging) return;
    win.style.left = (e.clientX - dx) + "px";
    win.style.top = (e.clientY - dy) + "px";
  });
  window.addEventListener("mouseup", function (e) {
    if (!dragging) return;
    dragging = false;
    var tr = els.tabBar.getBoundingClientRect();
    var inTabBar = e.clientX >= tr.left && e.clientX <= tr.right &&
      e.clientY >= tr.top && e.clientY <= tr.bottom;
    if (inTabBar) attachAppToDock(appId, true);
  });
}

function createFloatingWindow(appId, left, top) {
  var win = document.createElement("div");
  win.className = "floating-window";
  win.style.left = left + "px";
  win.style.top = top + "px";
  var head = document.createElement("div");
  head.className = "window-head";
  head.innerHTML = "<span>" + APP_TITLES[appId] + "</span>";
  var closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.textContent = "关闭并归位";
  head.appendChild(closeBtn);
  win.appendChild(head);
  var body = document.createElement("div");
  body.className = "window-body";
  win.appendChild(body);
  closeBtn.addEventListener("click", function () { attachAppToDock(appId, true); });
  win.addEventListener("mousedown", function () { bringFloatingToFront(win); });
  bindFloatingDragging(win, head, appId);
  return { win: win, body: body };
}

function detachAppFromDock(appId, clientX, clientY) {
  if (state.apps[appId].detached) return;
  var fw = createFloatingWindow(appId, clientX - 160, clientY - 40);
  var panel = getAppPanel(appId);
  panel.classList.add("show");
  fw.body.appendChild(panel);
  els.floatingLayer.appendChild(fw.win);
  state.apps[appId].detached = true;
  state.apps[appId].floatingWindow = fw.win;
  if (state.activeDocked === appId) {
    state.activeDocked = (APP_IDS.find(function (id) {
      return !state.apps[id].detached && id !== appId;
    })) || "dictionary";
  }
  renderDockPanels();
  updateTabVisualState();
  bringFloatingToFront(fw.win);
}

function attachAppToDock(appId, shouldActivate) {
  if (shouldActivate === undefined) shouldActivate = true;
  var info = state.apps[appId];
  if (!info.detached) { if (shouldActivate) activateDocked(appId); return; }
  var panel = getAppPanel(appId);
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
  var tabs = els.tabBar.querySelectorAll(".tab-item");
  tabs.forEach(function (tab) {
    var appId = tab.dataset.app;
    tab.draggable = DETACHABLE_APP_IDS.indexOf(appId) >= 0;
    tab.addEventListener("click", function () { activateDocked(appId); });
    if (DETACHABLE_APP_IDS.indexOf(appId) < 0) return;
    tab.addEventListener("dragstart", function () { state.dragTabAppId = appId; });
    tab.addEventListener("dragend", function (e) {
      var id = state.dragTabAppId;
      state.dragTabAppId = null;
      if (!id) return;
      var tr = els.tabBar.getBoundingClientRect();
      var inTabBar = e.clientX >= tr.left && e.clientX <= tr.right &&
        e.clientY >= tr.top && e.clientY <= tr.bottom;
      if (!inTabBar) detachAppToNativeWindow(id, e);
    });
  });
}

function bindSplitters() {
  document.documentElement.style.setProperty("--dict-left",
    clamp(loadRatio(STORAGE_KEYS.dictLeft, 50), 15, 85) + "%");
  document.documentElement.style.setProperty("--writing-main",
    clamp(loadRatio(STORAGE_KEYS.writingMain, 68), 25, 90) + "%");
  document.documentElement.style.setProperty("--writing-top",
    clamp(loadRatio(STORAGE_KEYS.writingTop, 72), 20, 90) + "%");

  function startDrag(splitterEl, onMove) {
    splitterEl.addEventListener("mousedown", function (e) {
      if (e.button !== 0) return;
      e.preventDefault();
      document.body.classList.add("splitter-active");
      function move(evt) { onMove(evt); }
      function up() {
        document.body.classList.remove("splitter-active");
        window.removeEventListener("mousemove", move);
        window.removeEventListener("mouseup", up);
      }
      window.addEventListener("mousemove", move);
      window.addEventListener("mouseup", up);
    });
  }

  function isNarrowLayout() { return window.matchMedia("(max-width: 980px)").matches; }

  startDrag(els.dictSplit, function (evt) {
    var rect = els.dictLayout.getBoundingClientRect();
    var raw = isNarrowLayout()
      ? ((evt.clientY - rect.top) / rect.height) * 100
      : ((evt.clientX - rect.left) / rect.width) * 100;
    var ratio = clamp(raw, 15, 85);
    document.documentElement.style.setProperty("--dict-left", ratio + "%");
    saveRatio(STORAGE_KEYS.dictLeft, ratio);
  });

  startDrag(els.writingMainSplit, function (evt) {
    var rect = els.writingTop.getBoundingClientRect();
    var raw = isNarrowLayout()
      ? ((evt.clientY - rect.top) / rect.height) * 100
      : ((evt.clientX - rect.left) / rect.width) * 100;
    var ratio = clamp(raw, 25, 90);
    document.documentElement.style.setProperty("--writing-main", ratio + "%");
    saveRatio(STORAGE_KEYS.writingMain, ratio);
  });

  startDrag(els.writingBottomSplit, function (evt) {
    var rect = els.writingWorkspace.getBoundingClientRect();
    var ratio = clamp(((evt.clientY - rect.top) / rect.height) * 100, 20, 90);
    document.documentElement.style.setProperty("--writing-top", ratio + "%");
    saveRatio(STORAGE_KEYS.writingTop, ratio);
  });
}
