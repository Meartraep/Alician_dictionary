function translatorStatusLabel(status) {
  if (status === "exact") return "精确";
  if (status === "approximate") return "近似";
  if (status === "unknown") return "缺词";
  if (status === "kept") return "保留";
  return status || "";
}

function getTranslatorWordRows(payload) {
  return (payload?.tokens || []).map(function (token, index) {
    return { token: token, index: index };
  }).filter(function (row) {
    return ["space", "punct"].indexOf(row.token.status) < 0;
  });
}

function normalizeTranslatorTokenOrder(payload) {
  var sourceOrder = getTranslatorWordRows(payload).map(function (row) { return row.index; });
  var valid = new Set(sourceOrder);
  var seen = new Set();
  var order = (state.translator.tokenOrder || []).filter(function (index) {
    if (!valid.has(index) || seen.has(index)) return false;
    seen.add(index);
    return true;
  });
  sourceOrder.forEach(function (index) {
    if (!seen.has(index)) order.push(index);
  });
  state.translator.tokenOrder = order;
  return order;
}

function getTranslatorTokensInDisplayOrder(payload) {
  var tokens = payload?.tokens || [];
  var order = normalizeTranslatorTokenOrder(payload);
  var cursor = 0;
  return tokens.map(function (token) {
    if (["space", "punct"].indexOf(token.status) >= 0) return token;
    var orderedToken = tokens[order[cursor]] || token;
    cursor += 1;
    return orderedToken;
  });
}

function composeTranslatorResult(payload) {
  if (!payload) return "";
  var tokens = getTranslatorTokensInDisplayOrder(payload);
  var direction = payload.direction || "zh_to_alician";
  if (direction === "alician_to_zh") {
    return tokens.map(function (token) {
      if (token.status === "space") return "";
      return token.target || "";
    }).join("").trim();
  }

  var out = [];
  for (var i = 0; i < tokens.length; i++) {
    var token = tokens[i];
    var status = token.status;
    var target = String(token.target || "");
    if (!target) continue;
    if (status === "space") {
      if (out.length && out[out.length - 1] !== " " && out[out.length - 1] !== "\n") out.push(" ");
      continue;
    }
    if (status === "punct") {
      while (out.length && out[out.length - 1] === " ") out.pop();
      out.push(target);
      out.push(" ");
      continue;
    }
    if (out.length && out[out.length - 1] !== " " && out[out.length - 1] !== "\n") out.push(" ");
    out.push(target);
  }
  return out.join("").trim();
}

function renderTranslatorOrderList(payload) {
  if (!els.translatorOrderList) return;
  if (!payload) {
    els.translatorOrderList.innerHTML =
      '<div class="result-meta">翻译后可在此拖动单词卡片，精调译文语序。</div>';
    return;
  }
  var tokens = payload.tokens || [];
  var order = normalizeTranslatorTokenOrder(payload);
  if (!order.length) {
    els.translatorOrderList.innerHTML = '<div class="result-item">暂无可排序的单词。</div>';
    return;
  }
  els.translatorOrderList.innerHTML = order.map(function (tokenIndex) {
    var token = tokens[tokenIndex] || {};
    return '<div class="translator-order-token ' + escapeHtml(token.status || "") +
      '" data-token-index="' + tokenIndex + '">' +
      '<span class="translator-token-source">' + escapeHtml(token.source || "") + '</span>' +
      '<span class="translator-arrow">→</span>' +
      '<span class="translator-token-target">' + escapeHtml(token.target || "") + '</span>' +
      '</div>';
  }).join("");
}

function applyTranslatorAlternative(tokenIndex, altIndex) {
  var payload = state.translator.lastResult;
  var token = payload?.tokens?.[tokenIndex];
  var alt = token?.alternatives?.[altIndex];
  if (!payload || !token || !alt) return;

  if (payload.direction === "alician_to_zh") {
    token.target = alt.explanation || alt.target || token.target;
  } else {
    token.target = alt.target || token.target;
  }
  token.explanation = alt.explanation || token.explanation || "";
  token.word_class = alt.word_class || token.word_class || "";
  token.confidence = alt.score != null ? Number(alt.score) : token.confidence;
  token.status = token.status === "unknown" ? "approximate" : token.status;
  token.note = "已手动选择候选词。";
  payload.result_text = composeTranslatorResult(payload);
  renderTranslatorResult(payload);
  saveModuleSnapshot("translator");
}

function renderTranslatorResult(payload) {
  if (!els.translatorDetails) return;
  if (!payload) {
    els.translatorDetails.innerHTML =
      '<div class="result-meta">缺词会显示为近似匹配或保留原词，方便后续人工校正。</div>';
    if (els.translatorStatus && !els.translatorStatus.textContent) {
      els.translatorStatus.textContent = "就绪";
    }
    renderTranslatorOrderList(null);
    return;
  }

  payload.result_text = composeTranslatorResult(payload);
  els.translatorOutput.value = payload.result_text;

  var stats = payload.stats || {};
  els.translatorStatus.textContent = (payload.message || "翻译完成。") +
    " 精确 " + (stats.exact || 0) +
    "，近似 " + (stats.approximate || 0) +
    "，缺词 " + (stats.unknown || 0);

  var rows = getTranslatorWordRows(payload);

  if (!rows.length) {
    els.translatorDetails.innerHTML = '<div class="result-item">暂无可显示的词条明细。</div>';
    renderTranslatorOrderList(payload);
    return;
  }

  els.translatorDetails.innerHTML = rows.map(function (row) {
    var token = row.token;
    var alternatives = (token.alternatives || []).slice(0, 5).map(function (alt, altIndex) {
      var score = alt.score != null ? " · " + Number(alt.score).toFixed(2) : "";
      var activeTarget = payload.direction === "alician_to_zh"
        ? (alt.explanation || alt.target || "") : (alt.target || "");
      var isActive = activeTarget === (token.target || "");
      return '<button class="translator-alt' + (isActive ? ' active' : '') +
        '" type="button" data-token-index="' + row.index +
        '" data-alt-index="' + altIndex + '">' + escapeHtml(alt.target || "") +
        '<span class="no-alic-font"> ' + escapeHtml(alt.explanation || "") +
        score + '</span></button>';
    }).join("");
    var meta = [
      translatorStatusLabel(token.status),
      token.word_class || "",
      token.method || "",
      token.confidence != null ? "置信 " + Number(token.confidence).toFixed(2) : "",
    ].filter(Boolean).join(" · ");
    return '<div class="translator-token ' + escapeHtml(token.status || "") + '">' +
      '<div class="translator-token-main">' +
      '<span class="translator-token-source">' + escapeHtml(token.source || "") + '</span>' +
      '<span class="translator-arrow">→</span>' +
      '<span class="translator-token-target">' + escapeHtml(token.target || "") + '</span>' +
      '</div>' +
      '<div class="result-meta no-alic-font">' + escapeHtml(meta) + '</div>' +
      (token.explanation ? '<div class="translator-explanation no-alic-font">' +
        escapeHtml(token.explanation) + '</div>' : '') +
      (token.note ? '<div class="result-meta no-alic-font">' +
        escapeHtml(token.note) + '</div>' : '') +
      (alternatives ? '<div class="translator-alts">' + alternatives + '</div>' : '') +
      '</div>';
  }).join("");
  renderTranslatorOrderList(payload);
}

function bindTranslatorSplitter() {
  if (!els.translatorSplit) return;
  var initial = clamp(loadRatio(STORAGE_KEYS.translatorOutput, 56), 22, 82);
  document.documentElement.style.setProperty("--translator-output", initial + "%");
  els.translatorSplit.addEventListener("mousedown", function (e) {
    if (e.button !== 0) return;
    e.preventDefault();
    document.body.classList.add("splitter-active");
    function move(evt) {
      var pane = els.translatorSplit.closest(".translator-result-pane");
      if (!pane) return;
      var rect = pane.getBoundingClientRect();
      var ratio = clamp(((evt.clientY - rect.top) / rect.height) * 100, 22, 82);
      document.documentElement.style.setProperty("--translator-output", ratio + "%");
      saveRatio(STORAGE_KEYS.translatorOutput, ratio);
    }
    function up() {
      document.body.classList.remove("splitter-active");
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    }
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  });

  if (!els.translatorMainSplit) return;
  var mainInitial = clamp(loadRatio(STORAGE_KEYS.translatorMain, 50), 22, 78);
  document.documentElement.style.setProperty("--translator-main", mainInitial + "%");
  els.translatorMainSplit.addEventListener("mousedown", function (e) {
    if (e.button !== 0) return;
    e.preventDefault();
    document.body.classList.add("splitter-active");
    function move(evt) {
      var layout = els.translatorMainSplit.closest(".translator-layout");
      if (!layout) return;
      var rect = layout.getBoundingClientRect();
      var stacked = window.matchMedia("(max-width: 980px)").matches;
      var ratio = stacked
        ? ((evt.clientY - rect.top) / rect.height) * 100
        : ((evt.clientX - rect.left) / rect.width) * 100;
      ratio = clamp(ratio, 22, 78);
      document.documentElement.style.setProperty("--translator-main", ratio + "%");
      saveRatio(STORAGE_KEYS.translatorMain, ratio);
    }
    function up() {
      document.body.classList.remove("splitter-active");
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    }
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  });
}

function clearTranslatorOrderDropState() {
  if (!els.translatorOrderList) return;
  els.translatorOrderList.querySelectorAll(".drag-before, .drag-after").forEach(function (node) {
    node.classList.remove("drag-before", "drag-after");
  });
}

function moveTranslatorToken(draggedIndex, targetIndex, insertAfter) {
  var payload = state.translator.lastResult;
  if (!payload || draggedIndex === targetIndex) return;
  var order = normalizeTranslatorTokenOrder(payload).slice();
  var from = order.indexOf(draggedIndex);
  if (from < 0) return;
  order.splice(from, 1);
  var target = order.indexOf(targetIndex);
  if (target < 0) return;
  order.splice(target + (insertAfter ? 1 : 0), 0, draggedIndex);
  state.translator.tokenOrder = order;
  payload.result_text = composeTranslatorResult(payload);
  renderTranslatorResult(payload);
  saveModuleSnapshot("translator");
}

function bindTranslatorOrderDragging() {
  if (!els.translatorOrderList) return;
  els.translatorOrderList.addEventListener("pointerdown", function (e) {
    if (e.button !== 0) return;
    var card = e.target.closest(".translator-order-token[data-token-index]");
    if (!card) return;
    var draggedIndex = Number(card.dataset.tokenIndex);
    var startX = e.clientX;
    var startY = e.clientY;
    var isDragging = false;
    state.translator.draggedTokenIndex = draggedIndex;

    function move(evt) {
      if (!isDragging && Math.hypot(evt.clientX - startX, evt.clientY - startY) < 4) return;
      isDragging = true;
      evt.preventDefault();
      card.classList.add("dragging");
      clearTranslatorOrderDropState();
      var listRect = els.translatorOrderList.getBoundingClientRect();
      if (evt.clientY < listRect.top + 28) els.translatorOrderList.scrollTop -= 12;
      else if (evt.clientY > listRect.bottom - 28) els.translatorOrderList.scrollTop += 12;
      var target = document.elementFromPoint(evt.clientX, evt.clientY)?.closest(
        ".translator-order-token[data-token-index]"
      );
      if (!target || target === card || !els.translatorOrderList.contains(target)) return;
      var rect = target.getBoundingClientRect();
      target.classList.add(evt.clientY >= rect.top + rect.height / 2 ? "drag-after" : "drag-before");
    }

    function up(evt) {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", cancel);
      if (isDragging) {
        var target = document.elementFromPoint(evt.clientX, evt.clientY)?.closest(
          ".translator-order-token[data-token-index]"
        );
        if (target && target !== card && els.translatorOrderList.contains(target)) {
          var rect = target.getBoundingClientRect();
          moveTranslatorToken(
            draggedIndex,
            Number(target.dataset.tokenIndex),
            evt.clientY >= rect.top + rect.height / 2
          );
        }
      }
      cancel();
    }

    function cancel() {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", cancel);
      state.translator.draggedTokenIndex = null;
      card.classList.remove("dragging");
      clearTranslatorOrderDropState();
    }

    window.addEventListener("pointermove", move, { passive: false });
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", cancel);
  });
}

function updateTranslatorPlaceholder() {
  var direction = els.translatorDirection?.value || "zh_to_alician";
  if (direction === "alician_to_zh") {
    els.translatorInput.placeholder = "输入爱丽丝语文本，例如：Kulu Nai";
    return;
  }
  if (direction === "auto") {
    els.translatorInput.placeholder = "输入中文或爱丽丝语，系统会自动识别方向";
    return;
  }
  els.translatorInput.placeholder = "输入中文自然语言，例如：升起的花";
}

async function runTranslator() {
  var text = String(els.translatorInput.value || "").trim();
  if (!text) {
    toast("请输入要翻译的内容。", "warn");
    return;
  }
  var direction = els.translatorDirection.value || "auto";
  state.translator.isBusy = true;
  els.translatorTranslateBtn.disabled = true;
  els.translatorStatus.textContent = "正在翻译...";
  saveModuleSnapshot("translator");
  try {
    var ret = await callApi("translator_translate", text, direction);
    state.translator.lastResult = ret;
    state.translator.tokenOrder = [];
    renderTranslatorResult(ret);
    saveModuleSnapshot("translator");
  } catch (err) {
    els.translatorStatus.textContent = "翻译失败";
    toast("翻译失败：" + err.message, "warn", 3600);
  } finally {
    state.translator.isBusy = false;
    els.translatorTranslateBtn.disabled = false;
  }
}

function swapTranslatorDirection() {
  var current = els.translatorDirection.value || "zh_to_alician";
  els.translatorDirection.value = current === "alician_to_zh" ? "zh_to_alician" : "alician_to_zh";
  state.translator.direction = els.translatorDirection.value;
  var output = String(els.translatorOutput.value || "").trim();
  if (output) {
    els.translatorInput.value = output;
    els.translatorOutput.value = "";
    state.translator.lastResult = null;
    state.translator.tokenOrder = [];
    renderTranslatorResult(null);
  }
  updateTranslatorPlaceholder();
  saveModuleSnapshot("translator");
}

function bindTranslatorEvents() {
  if (!els.translatorInput) return;
  bindTranslatorSplitter();
  bindTranslatorOrderDragging();
  updateTranslatorPlaceholder();
  renderTranslatorResult(null);

  els.translatorTranslateBtn.addEventListener("click", function () {
    runTranslator();
  });
  els.translatorSwapBtn.addEventListener("click", swapTranslatorDirection);
  els.translatorDirection.addEventListener("change", function () {
    state.translator.direction = els.translatorDirection.value || "zh_to_alician";
    updateTranslatorPlaceholder();
    saveModuleSnapshot("translator");
  });
  els.translatorInput.addEventListener("input", function () {
    state.translator.lastResult = null;
    state.translator.tokenOrder = [];
    renderTranslatorResult(null);
    saveModuleSnapshot("translator");
  });
  els.translatorInput.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      runTranslator();
    }
  });
  els.translatorDetails.addEventListener("click", function (e) {
    var btn = e.target.closest(".translator-alt[data-token-index][data-alt-index]");
    if (!btn) return;
    applyTranslatorAlternative(Number(btn.dataset.tokenIndex), Number(btn.dataset.altIndex));
  });
}
