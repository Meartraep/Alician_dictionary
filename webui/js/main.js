async function bootstrap() {
  try {
    var ret = await callApi("bootstrap");
    applyWritingSettings(ret?.writing_settings || state.writing.settings);
    applyAppSettings(ret?.app_settings || state.settings);
    els.writingStatus.textContent = ret?.writing_status || "";
    renderDictionaryHistory(ret?.dictionary_history || []);

    if (!state.isNativeDetached) {
      var initial = APP_IDS.indexOf(ret?.initial_tab) >= 0 && ret?.initial_tab !== "settings"
        ? ret.initial_tab : "dictionary";
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
    if (e.key === STORAGE_KEYS.dictSnapshot && state.isNativeDetached && state.nativeAppId === "dictionary") {
      restoreModuleSnapshot("dictionary", true);
      return;
    }
    if (e.key === STORAGE_KEYS.writingSnapshot && state.isNativeDetached && state.nativeAppId === "writing") {
      restoreModuleSnapshot("writing", false);
      return;
    }
    if (e.key === STORAGE_KEYS.translatorSnapshot && state.isNativeDetached && state.nativeAppId === "translator") {
      restoreModuleSnapshot("translator", false);
      return;
    }
    if (state.isNativeDetached) return;
    if (e.key === STORAGE_KEYS.writingSnapshot && state.apps.writing.detached) {
      restoreModuleSnapshot("writing", false);
    }
    if (e.key === STORAGE_KEYS.translatorSnapshot && state.apps.translator.detached) {
      restoreModuleSnapshot("translator", false);
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
  bindTranslatorEvents();
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
