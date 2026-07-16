var APP_IDS = ["dictionary", "writing", "translator", "dbmanager", "settings"];
var DETACHABLE_APP_IDS = ["dictionary", "writing", "translator", "dbmanager"];
var APP_TITLES = {
  dictionary: "词典工具",
  writing: "写作助手",
  translator: "翻译器",
  dbmanager: "数据库管理",
  settings: "设置",
};

var STORAGE_KEYS = {
  dictLeft: "ui.dict.leftRatio",
  writingMain: "ui.writing.mainRatio",
  writingTop: "ui.writing.topRatio",
  dictSnapshot: "ui.dictionary.snapshot",
  writingSnapshot: "ui.writing.snapshot",
  translatorSnapshot: "ui.translator.snapshot",
  translatorMain: "ui.translator.mainRatio",
  translatorOutput: "ui.translator.outputRatio",
};

function getWindowParams() {
  var source = window.location.search || window.location.hash.replace(/^#/, "");
  return new URLSearchParams(source);
}

var WINDOW_PARAMS = getWindowParams();
var NATIVE_APP_ID = WINDOW_PARAMS.get("app");
var IS_NATIVE_DETACHED = WINDOW_PARAMS.get("window") === "detached" && DETACHABLE_APP_IDS.indexOf(NATIVE_APP_ID) >= 0;

var state = {
  isNativeDetached: IS_NATIVE_DETACHED,
  nativeAppId: IS_NATIVE_DETACHED ? NATIVE_APP_ID : null,
  features: { lite: false, translator: true, fuzzy_search: true },
  activeDocked: "dictionary",
  zIndexSeed: 30,
  dragTabAppId: null,
  apps: {
    dictionary: { detached: false, floatingWindow: null },
    writing: { detached: false, floatingWindow: null },
    translator: { detached: false, floatingWindow: null },
    dbmanager: { detached: false, floatingWindow: null },
    settings: { detached: false, floatingWindow: null },
  },
  dbmanager: {
    currentTable: "", tables: [], fields: [], data: [],
    selectedIds: new Set(), globalResults: [], globalSelectedIndexes: new Set(),
    globalSearchVisible: true,
    editingRowId: "", editedValues: {}, dirtyRows: new Set(),
  },
  dictionary: { currentExamplesPayload: null, historyVisible: false },
  writing: {
    debounceTimer: null, checkSeq: 0, appliedSeq: 0, lastResult: null,
    settings: {
      strict_case: true, max_undo_steps: 100, excluded_words: [],
      dictionary_format_enabled: false, dictionary_format_separators: [":", "："],
    },
    selectedSidebarKey: "", infoPopup: null, isComposing: false,
  },
  translator: {
    direction: "zh_to_alician", lastResult: null, isBusy: false,
    tokenOrder: [], draggedTokenIndex: null,
  },
  settings: { alicFont: false, alicHoverEnabled: true, alicHoverDelay: 300 },
};

var els = {};

function saveRatio(key, value) {
  try { localStorage.setItem(key, String(value)); } catch (_) {}
}

function loadRatio(key, fallback) {
  try {
    var raw = localStorage.getItem(key);
    if (raw == null) return fallback;
    var val = Number(raw);
    return Number.isFinite(val) ? val : fallback;
  } catch (_) { return fallback; }
}

function saveJson(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) {}
}

function loadJson(key, fallback) {
  try {
    var raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (_) { return fallback; }
}
