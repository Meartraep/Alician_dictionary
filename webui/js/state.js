var APP_IDS = ["dictionary", "writing", "dbmanager", "settings"];
var DETACHABLE_APP_IDS = ["dictionary", "writing", "dbmanager"];
var APP_TITLES = {
  dictionary: "词典工具",
  writing: "写作助手",
  dbmanager: "数据库管理",
  settings: "设置",
};

var STORAGE_KEYS = {
  dictLeft: "ui.dict.leftRatio",
  writingMain: "ui.writing.mainRatio",
  writingTop: "ui.writing.topRatio",
  dictSnapshot: "ui.dictionary.snapshot",
  writingSnapshot: "ui.writing.snapshot",
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
    currentTable: "", tables: [], fields: [], data: [],
    selectedIds: new Set(), globalResults: [],
    editingRowId: "", editedValues: {}, dirtyRows: new Set(),
  },
  dictionary: { currentExamplesPayload: null, historyVisible: false },
  writing: {
    debounceTimer: null, checkSeq: 0, appliedSeq: 0, lastResult: null,
    settings: { strict_case: true, max_undo_steps: 100, excluded_words: [] },
    selectedSidebarKey: "", infoPopup: null, isComposing: false,
  },
  settings: { alicFont: false, alicHoverEnabled: true, alicHoverDelay: 300, dataDir: "" },
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
