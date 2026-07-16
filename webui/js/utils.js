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
var _alicHoverWordSpan = null;
var _alicHoverPending = null;

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
  if (!rootEl.contains(node)) return null;
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
  var wordRange = document.createRange();
  wordRange.setStart(node, start);
  wordRange.setEnd(node, end);

  // caretRangeFromPoint snaps to the nearest caret position, even when the
  // pointer is in surrounding whitespace.  Only accept a word when the
  // pointer is actually inside one of that word's rendered rectangles.
  var rects = wordRange.getClientRects();
  var pointInsideWord = false;
  for (var i = 0; i < rects.length; i++) {
    var rect = rects[i];
    if (rect.width > 0 && rect.height > 0 &&
        clientX >= rect.left && clientX <= rect.right &&
        clientY >= rect.top && clientY <= rect.bottom) {
      pointInsideWord = true;
      break;
    }
  }
  if (!pointInsideWord) return null;
  return { node: node, start: start, end: end, word: text.slice(start, end), range: wordRange };
}

function _alicHoverClear() {
  if (_alicHoverTimer !== null) { clearTimeout(_alicHoverTimer); _alicHoverTimer = null; }
  _alicHoverPending = null;
  _alicHoverClearWordSpan();
}

function _alicHoverRootAtPoint(clientX, clientY) {
  var el = document.elementFromPoint(clientX, clientY);
  if (!el || el.nodeType !== Node.ELEMENT_NODE) return null;
  if (el.closest(".no-alic-font, button, input, textarea, select")) return null;

  var roots = [els.writingEditor, els.dictLayout, els.dictExamples, els.writingSidebar,
    els.writingExplanation, els.translatorDetails, els.translatorOrderList, els.modalRoot];
  for (var i = 0; i < roots.length; i++) {
    if (roots[i] && roots[i].contains(el)) return roots[i];
  }
  return null;
}

function _alicSameWordRange(a, b) {
  return Boolean(a && b && a.node === b.node && a.start === b.start && a.end === b.end);
}

function _alicHoverDelay() {
  var delay = Number(state.settings.alicHoverDelay);
  return Number.isFinite(delay) ? clamp(delay, 0, 1000) : 300;
}

function _alicHoverMove(e) {
  if (!state.settings.alicHoverEnabled) { _alicHoverClear(); return; }

  var root = _alicHoverRootAtPoint(e.clientX, e.clientY);
  var wordRange = root ? _alicGetWordRangeAtPoint(root, e.clientX, e.clientY) : null;
  if (!wordRange) { _alicHoverClear(); return; }

  // The active wrapper is itself now the hit text node. Keep it only while
  // the pointer remains geometrically inside that exact wrapper.
  if (_alicHoverWordSpan && _alicHoverWordSpan.contains(wordRange.node)) return;

  if (_alicSameWordRange(_alicHoverPending, wordRange)) {
    _alicHoverPending.clientX = e.clientX;
    _alicHoverPending.clientY = e.clientY;
    return;
  }

  // Removing the previous wrapper normalizes text nodes, invalidating ranges
  // captured before cleanup. Recompute the target after every DOM restoration.
  _alicHoverClear();
  root = _alicHoverRootAtPoint(e.clientX, e.clientY);
  wordRange = root ? _alicGetWordRangeAtPoint(root, e.clientX, e.clientY) : null;
  if (!wordRange) return;

  wordRange.root = root;
  wordRange.clientX = e.clientX;
  wordRange.clientY = e.clientY;
  _alicHoverPending = wordRange;
  _alicHoverTimer = setTimeout(function () {
    _alicHoverTimer = null;
    var pending = _alicHoverPending;
    if (!pending || _alicHoverWordSpan) return;

    // Revalidate at firing time so scrolling, rerendering, or layout changes
    // during the delay cannot apply a font to a stale word.
    var currentRoot = _alicHoverRootAtPoint(pending.clientX, pending.clientY);
    var current = currentRoot
      ? _alicGetWordRangeAtPoint(currentRoot, pending.clientX, pending.clientY)
      : null;
    if (currentRoot !== pending.root || !_alicSameWordRange(pending, current)) {
      _alicHoverPending = null;
      return;
    }

    var span = document.createElement("span");
    try { current.range.surroundContents(span); } catch (_) {
      _alicHoverPending = null;
      return;
    }
    _alicHoverPending = null;
    _alicHoverWordSpan = span;
    span.classList.add(state.settings.alicFont ? "alic-hover-system" : "alic-hover-alic");
  }, _alicHoverDelay());
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
  window.addEventListener("blur", _alicHoverClear);
  window.addEventListener("scroll", _alicHoverClear, true);
}
