function translatorStatusLabel(status) {
  if (status === "exact") return "精确";
  if (status === "approximate") return "近似";
  if (status === "unknown") return "缺词";
  if (status === "kept") return "保留";
  return status || "";
}

function composeTranslatorResult(payload) {
  if (!payload) return "";
  var tokens = payload.tokens || [];
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
    return;
  }

  if (typeof payload.result_text === "string") {
    els.translatorOutput.value = payload.result_text;
  }

  var stats = payload.stats || {};
  els.translatorStatus.textContent = (payload.message || "翻译完成。") +
    " 精确 " + (stats.exact || 0) +
    "，近似 " + (stats.approximate || 0) +
    "，缺词 " + (stats.unknown || 0);

  var rows = (payload.tokens || []).map(function (token, index) {
    return { token: token, index: index };
  }).filter(function (row) {
    return ["space", "punct"].indexOf(row.token.status) < 0;
  });

  if (!rows.length) {
    els.translatorDetails.innerHTML = '<div class="result-item">暂无可显示的词条明细。</div>';
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
    renderTranslatorResult(null);
  }
  updateTranslatorPlaceholder();
  saveModuleSnapshot("translator");
}

function bindTranslatorEvents() {
  if (!els.translatorInput) return;
  bindTranslatorSplitter();
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
