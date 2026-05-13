async function bootstrap() {
  try {
    var ret = await callApi("bootstrap");
    applyWritingSettings(ret?.writing_settings || state.writing.settings);
    applyAppSettings(ret?.app_settings || state.settings);
    els.writingStatus.textContent = ret?.writing_status || "";
    renderDictionaryHistory(ret?.dictionary_history || []);

    if (!state.isNativeDetached) {
      var initial = ret?.initial_tab === "writing" ? "writing" : "dictionary";
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
    toast("初始化失败：" + err.message, "warn", 3600);
  }
}

function bindGlobal() {
  els.modalCloseBtn.addEventListener("click", closeModal);
  els.modalRoot.addEventListener("click", function (e) {
    if (e.target === els.modalRoot) closeModal();
  });
  window.addEventListener("storage", function (e) {
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
  bindAlicHover();
  renderDockPanels();
  updateTabVisualState();
  bootstrap();
}

if (document.readyState === "loading") {
  window.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
