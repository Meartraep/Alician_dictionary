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

var pywebviewApiReady = null;

function getPywebviewApi() {
  var api = window.pywebview?.api;
  return api && typeof api === "object" ? api : null;
}

function waitForPywebviewApi(timeoutMs) {
  timeoutMs = timeoutMs || 8000;
  var current = getPywebviewApi();
  if (current) return Promise.resolve(current);
  if (pywebviewApiReady) return pywebviewApiReady;

  pywebviewApiReady = new Promise(function (resolve, reject) {
    var settled = false, pollTimer = null, timeoutTimer = null;

    function cleanup() {
      window.removeEventListener("pywebviewready", onReady);
      if (pollTimer !== null) window.clearInterval(pollTimer);
      if (timeoutTimer !== null) window.clearTimeout(timeoutTimer);
    }

    function finish(api, error) {
      if (settled) return;
      settled = true;
      cleanup();
      pywebviewApiReady = error ? null : Promise.resolve(api);
      if (error) { reject(error); return; }
      resolve(api);
    }

    function checkReady() {
      var api = getPywebviewApi();
      if (api) finish(api);
    }

    function onReady() { checkReady(); }

    window.addEventListener("pywebviewready", onReady);
    pollTimer = window.setInterval(checkReady, 50);
    timeoutTimer = window.setTimeout(function () {
      finish(null, new Error("Python API unavailable"));
    }, timeoutMs);
    checkReady();
  });
  return pywebviewApiReady;
}

async function waitForPywebviewMethod(method, timeoutMs) {
  timeoutMs = timeoutMs || 8000;
  var started = Date.now();
  var api = await waitForPywebviewApi(timeoutMs);
  while (Date.now() - started < timeoutMs) {
    var fn = api?.[method];
    if (typeof fn === "function") return fn.bind(api);
    await new Promise(function (resolve) { window.setTimeout(resolve, 50); });
    api = getPywebviewApi() || api;
  }
  throw new Error("Python API method unavailable: " + method);
}

async function callApi(method, ...args) {
  var fn = await waitForPywebviewMethod(method);
  return fn(...args);
}

function toast(message, kind, duration) {
  kind = kind || "info";
  duration = duration || 2200;
  var node = document.createElement("div");
  node.className = "toast " + kind;
  node.textContent = message;
  els.toastRoot.appendChild(node);
  setTimeout(function () { node.remove(); }, duration);
}

var _alicHoverTimer = null;
var _alicHoverEl = null;
var _alicHoverWordSpan = null;

function _alicHoverClearWordSpan() {
  if (_alicHoverWordSpan && _alicHoverWordSpan.parentNode) {
    var parent = _alicHoverWordSpan.parentNode;
    _alicHoverWordSpan.replaceWith(document.createTextNode(_alicHoverWordSpan.textContent));
    parent.normalize();
  }
  _alicHoverWordSpan = null;
}

function _alicGetWordRangeAtPoint(rootEl, clientX, clientY) {
  var range = null;
  if (document.caretRangeFromPoint) {
    range = document.caretRangeFromPoint(clientX, clientY);
  } else if (document.caretPositionFromPoint) {
    var cp = document.caretPositionFromPoint(clientX, clientY);
    if (cp) { range = document.createRange(); range.setStart(cp.offsetNode, cp.offset); range.collapse(true); }
  }
  if (!range) return null;
  var node = range.startContainer;
  if (node.nodeType !== Node.TEXT_NODE) return null;
  var text = node.nodeValue || "";
  var offset = clamp(range.startOffset, 0, text.length);
  var start = offset;
  while (start > 0 && /[^\s.,;:!?()[\]{}"'<>…—\-–\u2018\u2019\u201C\u201D]/.test(text[start - 1])) {
    start--;
  }
  var end = offset;
  while (end < text.length && /[^\s.,;:!?()[\]{}"'<>…—\-–\u2018\u2019\u201C\u201D]/.test(text[end])) {
    end++;
  }
  if (start === end) return null;
  return { node: node, start: start, end: end, word: text.slice(start, end) };
}

function _alicHoverClear() {
  if (_alicHoverTimer) { clearTimeout(_alicHoverTimer); _alicHoverTimer = null; }
  _alicHoverClearWordSpan();
  if (_alicHoverEl) {
    _alicHoverEl.classList.remove("alic-hover-system", "alic-hover-alic");
    _alicHoverEl = null;
  }
}

function _alicHoverMove(e) {
  if (!state.settings.alicHoverEnabled) { _alicHoverClear(); return; }

  var range = null;
  if (document.caretRangeFromPoint) {
    range = document.caretRangeFromPoint(e.clientX, e.clientY);
  } else if (document.caretPositionFromPoint) {
    var cp = document.caretPositionFromPoint(e.clientX, e.clientY);
    if (cp) { range = document.createRange(); range.setStart(cp.offsetNode, cp.offset); range.collapse(true); }
  }

  var el = null;
  if (range) {
    el = range.startContainer.nodeType === Node.TEXT_NODE
      ? range.startContainer.parentElement
      : range.startContainer;
  }
  if (!el) el = document.elementFromPoint(e.clientX, e.clientY);
  if (!el) { _alicHoverClear(); return; }

  var tn = el.tagName;
  if (tn === "BUTTON" || tn === "INPUT" || tn === "TEXTAREA" || tn === "SELECT") {
    _alicHoverClear();
    return;
  }
  if (el.closest(".no-alic-font") || el.closest("button") || el.closest("input") || el.closest("textarea")) {
    _alicHoverClear();
    return;
  }

  var inEditor = els.writingEditor && els.writingEditor.contains(el);

  if (inEditor) {
    var wordRange = _alicGetWordRangeAtPoint(els.writingEditor, e.clientX, e.clientY);
    if (wordRange) {
      if (_alicHoverWordSpan && _alicHoverWordSpan.parentNode) {
        var currentText = _alicHoverWordSpan.textContent;
        var currentWord = currentText || "";
        if (currentWord === wordRange.word) return;
      }
      _alicHoverClear();
      var wrapRange = document.createRange();
      wrapRange.setStart(wordRange.node, wordRange.start);
      wrapRange.setEnd(wordRange.node, wordRange.end);
      var span = document.createElement("span");
      var delay = state.settings.alicHoverDelay || 300;
      _alicHoverTimer = setTimeout(function () {
        if (!_alicHoverWordSpan) {
          try { wrapRange.surroundContents(span); } catch (_) {}
          if (span.parentNode) {
            _alicHoverWordSpan = span;
            if (state.settings.alicFont) {
              _alicHoverWordSpan.classList.add("alic-hover-system");
            } else {
              _alicHoverWordSpan.classList.add("alic-hover-alic");
            }
          }
        }
      }, delay);
    } else {
      _alicHoverClear();
    }
    return;
  }

  if (el === _alicHoverEl) return;
  _alicHoverClear();
  _alicHoverEl = el;
  var delay = state.settings.alicHoverDelay || 300;
  _alicHoverTimer = setTimeout(function () {
    if (!_alicHoverEl) return;
    if (state.settings.alicFont) {
      _alicHoverEl.classList.add("alic-hover-system");
    } else {
      _alicHoverEl.classList.add("alic-hover-alic");
    }
  }, delay);
}

function bindAlicHover() {
  var panels = [els.dictLayout, els.dictExamples, els.writingEditor, els.writingSidebar,
    els.writingExplanation, els.translatorDetails, els.translatorOrderList];
  for (var i = 0; i < panels.length; i++) {
    var panel = panels[i];
    if (!panel) continue;
    panel.addEventListener("mousemove", _alicHoverMove);
    panel.addEventListener("mouseleave", _alicHoverClear);
  }
  if (els.modalRoot) {
    els.modalRoot.addEventListener("mousemove", _alicHoverMove);
    els.modalRoot.addEventListener("mouseleave", _alicHoverClear);
  }
}
