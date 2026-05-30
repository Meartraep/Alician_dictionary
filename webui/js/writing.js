function locateDomPointByTextOffset(root, targetOffset) {
  var total = getEditorText().length, offset = clamp(targetOffset, 0, total);
  var consumed = 0, found = null;
  (function walk(node) {
    if (found) return;
    if (node.nodeType === Node.TEXT_NODE) {
      var text = node.nodeValue || "", len = text.length;
      if (offset <= consumed + len) { found = { node: node, offset: offset - consumed }; return; }
      consumed += len; return;
    }
    if (node.nodeType === Node.ELEMENT_NODE && node.tagName === "BR") {
      if (offset <= consumed + 1) {
        var p = node.parentNode;
        found = { node: p, offset: Array.prototype.indexOf.call(p.childNodes, node) + 1 };
        return;
      }
      consumed += 1; return;
    }
    var children = node.childNodes || [];
    for (var i = 0; i < children.length; i++) walk(children[i]);
  })(root);
  if (found) return found;
  return { node: root, offset: root.childNodes.length };
}

function setCaretRangeByOffset(root, start, end) {
  if (end === undefined) end = start;
  var s = locateDomPointByTextOffset(root, start);
  var e = locateDomPointByTextOffset(root, end);
  var range = document.createRange();
  range.setStart(s.node, s.offset);
  range.setEnd(e.node, e.offset);
  var sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
}

function getCaretOffset(root) {
  var sel = window.getSelection();
  if (!sel || !sel.rangeCount) return 0;
  var range = sel.getRangeAt(0);
  var probe = range.cloneRange();
  probe.selectNodeContents(root);
  probe.setEnd(range.endContainer, range.endOffset);
  return probe.toString().length;
}

function offsetFromPoint(root, clientX, clientY) {
  var range = null;
  if (document.caretRangeFromPoint) {
    range = document.caretRangeFromPoint(clientX, clientY);
  } else if (document.caretPositionFromPoint) {
    var pos = document.caretPositionFromPoint(clientX, clientY);
    if (pos) { range = document.createRange(); range.setStart(pos.offsetNode, pos.offset); range.collapse(true); }
  }
  if (!range) return getCaretOffset(root);
  var probe = document.createRange();
  probe.selectNodeContents(root);
  probe.setEnd(range.endContainer, range.endOffset);
  return probe.toString().length;
}

function buildHighlightTypeArray(text, unknownRanges, lowstatRanges) {
  var arr = new Array(text.length).fill(0);
  for (var i = 0; i < (lowstatRanges || []).length; i++) {
    var s = clamp(Number(lowstatRanges[i][0]), 0, text.length);
    var e = clamp(Number(lowstatRanges[i][1]), s, text.length);
    for (var j = s; j < e; j++) arr[j] = Math.max(arr[j], 1);
  }
  for (var i = 0; i < (unknownRanges || []).length; i++) {
    var s = clamp(Number(unknownRanges[i][0]), 0, text.length);
    var e = clamp(Number(unknownRanges[i][1]), s, text.length);
    for (var j = s; j < e; j++) arr[j] = 2;
  }
  return arr;
}

function renderColoredEditorHtml(text, unknownRanges, lowstatRanges) {
  var source = String(text || "");
  var types = buildHighlightTypeArray(source, unknownRanges, lowstatRanges);
  var html = "", active = 0;
  function closeSpan() { if (active !== 0) html += '</span>'; active = 0; }
  function openSpan(t) {
    if (t === 2) html += '<span class="mark-unknown" data-hl="unknown" style="color:#b00020;font-weight:700">';
    if (t === 1) html += '<span class="mark-lowstat" data-hl="lowstat" style="color:#0d4ba8;font-weight:700">';
    active = t;
  }
  for (var i = 0; i < source.length; i++) {
    var t = types[i];
    if (t !== active) { closeSpan(); if (t !== 0) openSpan(t); }
    var ch = source[i];
    html += ch === "\n" ? "<br>" : escapeHtml(ch);
  }
  closeSpan();
  return html;
}

function renderWritingSidebar(items) {
  if (!Array.isArray(items) || items.length === 0) {
    els.writingSidebar.innerHTML = '<div class="sidebar-item">暂无高亮词。</div>';
    return;
  }
  els.writingSidebar.innerHTML = items.map(function (it, idx) {
    var reasons = (it.reasons || []).join("，");
    var active = state.writing.selectedSidebarKey === (it.pos + "|" + it.display) ? " active" : "";
    return '<div class="sidebar-item ' + escapeHtml(it.type || "unknown") + active +
      '" data-index="' + idx + '" data-pos="' + (Number(it.pos) || 0) +
      '" data-word="' + escapeHtml(it.display || "") +
      '" data-type="' + escapeHtml(it.type || "unknown") + '">' +
      '<div>' + escapeHtml(it.display || "") + '</div>' +
      '<div class="result-meta">' + (reasons ? escapeHtml(reasons) : "无附加说明") + '</div>' +
      '<div class="result-meta"><span class="no-alic-font">count: ' + (Number(it.count) || 0) +
      ' | variety: ' + (Number(it.variety) || 0) + '</span></div></div>';
  }).join("");
}

async function renderLookupToBottom(selectedText) {
  var text = String(selectedText || "").trim();
  if (!text) return;
  try {
    var ret = await callApi("writing_lookup", text);
    if (!ret?.ok) { els.writingExplanation.textContent = ret?.message || "未找到信息。"; return; }
    var expl = (ret.explanations || []).map(function (it) {
      return '<div class="result-item"><strong>' + escapeHtml(it.word || "") +
        '</strong>：' + escapeHtml(it.explanation || "未找到释义") + '</div>';
    }).join("");
    var simil = (ret.similar_words || []).map(function (it) {
      return '<div class="result-item">建议：' + escapeHtml(it.word || "") +
        ' → ' + escapeHtml(it.similar_word || "") + '（相似度 ' + (it.score ?? 0) + '）<br>' +
        escapeHtml(it.explanation || "") + '</div>';
    }).join("");
    els.writingExplanation.innerHTML = '<div class="explanation-stack">' +
      '<div class="result-section-title">释义与建议</div>' +
      (expl || '<div class="result-item">无释义信息</div>') + simil + '</div>';
  } catch (err) { els.writingExplanation.textContent = "查询失败：" + err.message; }
}

function renderLowstatDetailsToBottom(item) {
  var reasons = Array.isArray(item?.reasons) && item.reasons.length ? item.reasons.join("，") : "无";
  els.writingExplanation.innerHTML = '<div class="explanation-stack">' +
    '<div class="result-section-title">高亮原因与数值</div>' +
    '<div class="result-item"><strong>单词：</strong>' + escapeHtml(item?.display || "") + '</div>' +
    '<div class="result-item"><strong>类型：</strong>' +
    (item?.type === "lowstat" ? "蓝色低词频词" : "红色未知词") + '</div>' +
    '<div class="result-item"><strong>词频：</strong><span class="no-alic-font">' + (Number(item?.count) || 0) + '</span></div>' +
    '<div class="result-item"><strong>泛度：</strong><span class="no-alic-font">' + (Number(item?.variety) || 0) + '</span></div>' +
    '<div class="result-item"><strong>count：</strong><span class="no-alic-font">' + (Number(item?.count) || 0) + '</span></div>' +
    '<div class="result-item"><strong>variety：</strong><span class="no-alic-font">' + (Number(item?.variety) || 0) + '</span></div>' +
    '<div class="result-item"><strong>原因：</strong>' + escapeHtml(reasons) + '</div></div>';
}

function closeInfoPopup() {
  if (!state.writing.infoPopup) return;
  state.writing.infoPopup.remove();
  state.writing.infoPopup = null;
}

function showInfoPopup(item, clientX, clientY) {
  closeInfoPopup();
  var popup = document.createElement("div");
  popup.className = "info-popup";
  var reasons = Array.isArray(item.reasons) && item.reasons.length ? item.reasons.join("，") : "无";
  popup.innerHTML = '<div class="info-popup-title">' + escapeHtml(item.display || "") + '</div>' +
    '<div>类型：' + (item.type === "lowstat" ? "蓝色低词频词" : "红色未知词") + '</div>' +
    '<div>词频：<span class="no-alic-font">' + (Number(item.count) || 0) + '</span></div>' +
    '<div>泛度：<span class="no-alic-font">' + (Number(item.variety) || 0) + '</span></div>' +
    '<div>原因：' + escapeHtml(reasons) + '</div>';
  popup.style.left = (clientX + 8) + "px";
  popup.style.top = (clientY + 8) + "px";
  document.body.appendChild(popup);
  state.writing.infoPopup = popup;
}

function findSidebarItemAtOffset(offset) {
  var items = state.writing.lastResult?.sidebar_items || [];
  if (!items.length) return null;
  for (var i = 0; i < items.length; i++) {
    var it = items[i];
    var s = Number(it.pos) || 0;
    var e = s + String(it.display || "").length;
    if (offset >= s && offset < e) return it;
  }
  var nearest = null, best = Number.POSITIVE_INFINITY;
  for (var i = 0; i < items.length; i++) {
    var d = Math.abs((Number(items[i].pos) || 0) - offset);
    if (d < best) { best = d; nearest = items[i]; }
  }
  return best <= 2 ? nearest : null;
}

async function runWritingCheck(immediate) {
  immediate = immediate || false;
  async function perform() {
    if (state.writing.isComposing) return;
    var text = getEditorText(), seq = ++state.writing.checkSeq;
    try {
      var ret = await callApi("writing_check_text", text);
      if (seq !== state.writing.checkSeq || state.writing.isComposing) return;
      state.writing.appliedSeq = seq;
      state.writing.lastResult = ret;
      var caret = getCaretOffset(els.writingEditor);
      els.writingEditor.innerHTML = renderColoredEditorHtml(
        text, ret.unknown_ranges || [], ret.lowstat_ranges || []);
      setCaretRangeByOffset(els.writingEditor, clamp(caret, 0, getEditorText().length));
      renderWritingSidebar(ret.sidebar_items || []);
      els.writingStatus.textContent = ret.status || "";
    } catch (err) {
      if (seq !== state.writing.checkSeq) return;
      toast("检查失败：" + err.message, "warn", 3200);
    }
  }
  if (immediate) { clearTimeout(state.writing.debounceTimer); await perform(); return; }
  clearTimeout(state.writing.debounceTimer);
  state.writing.debounceTimer = setTimeout(function () { perform(); }, 280);
}

function applyWritingSettings(settings) {
  state.writing.settings = settings || state.writing.settings;
  els.settingsStrictCase.checked = Boolean(state.writing.settings.strict_case);
  els.settingsUndo.value = Number(state.writing.settings.max_undo_steps) || 100;
  renderExcludedWords(state.writing.settings.excluded_words || []);
}

function applyAppSettings(settings) {
  state.settings.alicFont = Boolean(settings?.alic_font);
  state.settings.alicHoverEnabled = settings?.alic_hover_enabled != null ? Boolean(settings.alic_hover_enabled) : true;
  state.settings.alicHoverDelay = settings?.alic_hover_delay != null ? Number(settings.alic_hover_delay) || 300 : 300;
  state.settings.dataDir = String(settings?.data_dir || "");
  if (els.alicFontToggle) els.alicFontToggle.checked = state.settings.alicFont;
  if (els.alicHoverToggle) els.alicHoverToggle.checked = state.settings.alicHoverEnabled;
  if (els.alicHoverDelaySlider) els.alicHoverDelaySlider.value = state.settings.alicHoverDelay;
  if (els.alicHoverDelayLabel) els.alicHoverDelayLabel.textContent = state.settings.alicHoverDelay + " ms";
  if (els.dataDirInput) els.dataDirInput.value = state.settings.dataDir;
  if (els.dataDirNote) els.dataDirNote.textContent = state.settings.dataDir ? "自定义数据目录（更改后需重启生效）" : "程序运行时数据的存放位置";
  if (els.updateCheckStatus) els.updateCheckStatus.textContent = String(settings?.update_check_status || "就绪");
  if (els.forceDownloadBtn) {
    var showBtn = String(settings?.update_check_status || "") === "云端版本未变化，无需下载";
    els.forceDownloadBtn.classList.toggle("hidden", !showBtn);
  }
  document.body.classList.toggle("alic-font", state.settings.alicFont);
}

function renderExcludedWords(words) {
  var source = Array.isArray(words) ? words : [];
  var normalized = [], seen = new Set();
  for (var i = 0; i < source.length; i++) {
    var word = String(source[i] || "").trim();
    if (!word || seen.has(word)) continue;
    seen.add(word);
    normalized.push(word);
  }
  state.writing.settings.excluded_words = normalized;
  if (!normalized.length) {
    els.excludedList.innerHTML = '<span class="result-meta">暂无排除词</span>';
    return;
  }
  els.excludedList.innerHTML = normalized.map(function (w) {
    return '<span class="excluded-tag" data-word="' + escapeHtml(w) + '">' +
      escapeHtml(w) + '<button class="ghost small excluded-del" type="button" data-word="' +
      escapeHtml(w) + '">删除</button></span>';
  }).join("");
}

function centerEditorSelection() {
  var sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return;
  var range = sel.getRangeAt(0).cloneRange();
  var editor = els.writingEditor;
  var editorRect = editor.getBoundingClientRect();
  var rect = range.getBoundingClientRect();
  if ((!rect || rect.height === 0) && range.getClientRects().length > 0) rect = range.getClientRects()[0];
  var targetCenterY = null;
  if (rect && rect.height > 0) {
    targetCenterY = rect.top - editorRect.top + editor.scrollTop + rect.height / 2;
  } else {
    var sNode = range.startContainer?.nodeType === Node.TEXT_NODE
      ? range.startContainer.parentElement : range.startContainer;
    if (sNode && editor.contains(sNode)) {
      var nr = sNode.getBoundingClientRect();
      targetCenterY = nr.top - editorRect.top + editor.scrollTop + nr.height / 2;
    }
  }
  if (targetCenterY == null) return;
  editor.scrollTop = Math.max(0, targetCenterY - editor.clientHeight / 2);
}

function syncSidebarActiveClasses() {
  var key = state.writing.selectedSidebarKey;
  var nodes = els.writingSidebar.querySelectorAll(".sidebar-item[data-pos][data-word]");
  nodes.forEach(function (node) {
    var nodeKey = (node.dataset.pos || "0") + "|" + (node.dataset.word || "");
    node.classList.toggle("active", key !== "" && nodeKey === key);
  });
}

function activateSidebarWord(item) {
  if (!item) return;
  state.writing.selectedSidebarKey = item.pos + "|" + item.display;
  syncSidebarActiveClasses();
}

function selectSidebarWord(item) {
  if (!item) return;
  var start = Number(item.pos) || 0;
  var len = String(item.display || "").length;
  var maxLen = getEditorText().length;
  activateSidebarWord(item);
  els.writingEditor.focus();
  setCaretRangeByOffset(els.writingEditor, clamp(start, 0, maxLen), clamp(start + len, 0, maxLen));
  requestAnimationFrame(function () {
    requestAnimationFrame(function () { centerEditorSelection(); });
  });
}

function bindWritingEvents() {
  els.writingEditor.addEventListener("compositionstart", function () {
    state.writing.isComposing = true; state.writing.checkSeq += 1;
    clearTimeout(state.writing.debounceTimer);
  });
  els.writingEditor.addEventListener("compositionend", function () {
    state.writing.isComposing = false; closeInfoPopup();
    saveModuleSnapshot("writing"); runWritingCheck(false);
  });
  els.writingEditor.addEventListener("input", function (e) {
    closeInfoPopup();
    if (state.writing.isComposing || e.isComposing) return;
    saveModuleSnapshot("writing"); runWritingCheck(false);
  });
  els.writingEditor.addEventListener("contextmenu", async function (e) {
    var sel = String(window.getSelection()?.toString() || "").trim();
    if (sel) { e.preventDefault(); closeInfoPopup(); await renderLookupToBottom(sel); return; }
    var offset = offsetFromPoint(els.writingEditor, e.clientX, e.clientY);
    var item = findSidebarItemAtOffset(offset);
    if (!item) { closeInfoPopup(); return; }
    if (item.type === "lowstat" || item.type === "unknown") {
      e.preventDefault(); showInfoPopup(item, e.clientX, e.clientY);
    }
  });
  document.addEventListener("mousedown", function (e) {
    if (!state.writing.infoPopup) return;
    if (state.writing.infoPopup.contains(e.target)) return;
    closeInfoPopup();
  });
  els.writingSidebar.addEventListener("click", function (e) {
    var node = e.target.closest(".sidebar-item[data-index]");
    if (!node) return;
    var idx = Number(node.dataset.index);
    var item = state.writing.lastResult?.sidebar_items?.[idx];
    activateSidebarWord(item);
  });
  els.writingSidebar.addEventListener("dblclick", function (e) {
    var node = e.target.closest(".sidebar-item[data-index]");
    if (!node) return;
    var idx = Number(node.dataset.index);
    var item = state.writing.lastResult?.sidebar_items?.[idx];
    if (!item) return;
    selectSidebarWord(item);
    if (item.type === "lowstat") renderLowstatDetailsToBottom(item);
    else renderLookupToBottom(item.display);
  });
  els.writingImportBtn.addEventListener("click", function () {
    els.fileLoader.value = ""; els.fileLoader.click();
  });
  els.fileLoader.addEventListener("change", async function () {
    var file = els.fileLoader.files?.[0];
    if (!file) return;
    var text = await file.text();
    els.writingEditor.textContent = text;
    state.writing.selectedSidebarKey = ""; closeInfoPopup();
    saveModuleSnapshot("writing");
    if (getEditorText().trim()) await runWritingCheck(true);
    toast("已导入：" + file.name);
  });
  els.writingExportBtn.addEventListener("click", async function () {
    try {
      var ret = await callApi("writing_export_text", getEditorText(), "writing_assistant.txt");
      toast(ret?.message || "导出完成", ret?.ok ? "info" : "warn", 3200);
    } catch (err) { toast("导出失败：" + err.message, "warn", 3200); }
  });
  els.writingSettingsBtn.addEventListener("click", async function () {
    els.writingSettingsPanel.classList.toggle("hidden");
    if (els.writingSettingsPanel.classList.contains("hidden")) return;
    try {
      var l = await callApi("writing_get_settings");
      applyWritingSettings(l || state.writing.settings);
    } catch (_) { renderExcludedWords(state.writing.settings.excluded_words || []); }
  });
  els.settingsCloseBtn.addEventListener("click", function () {
    els.writingSettingsPanel.classList.add("hidden");
  });
  els.excludedAddBtn.addEventListener("click", function () {
    var v = String(els.excludedInput.value || "").trim();
    if (!v) return;
    var cur = new Set(state.writing.settings.excluded_words || []);
    cur.add(v);
    renderExcludedWords(Array.from(cur));
    els.excludedInput.value = "";
  });
  els.excludedList.addEventListener("click", function (e) {
    var btn = e.target.closest(".excluded-del[data-word]");
    if (!btn) return;
    var w = btn.dataset.word || "";
    renderExcludedWords((state.writing.settings.excluded_words || []).filter(function (x) { return x !== w; }));
  });
  els.settingsSaveBtn.addEventListener("click", async function () {
    var p = {
      strict_case: Boolean(els.settingsStrictCase.checked),
      max_undo_steps: Number(els.settingsUndo.value) || 100,
      excluded_words: state.writing.settings.excluded_words || [],
    };
    try {
      var ret = await callApi("writing_save_settings", p);
      if (ret?.ok) {
        applyWritingSettings(ret.settings || p);
        els.writingStatus.textContent = ret.status || "";
        els.writingSettingsPanel.classList.add("hidden");
        await runWritingCheck(true);
      }
      toast(ret?.message || "设置已保存", ret?.ok ? "info" : "warn");
    } catch (err) { toast("保存设置失败：" + err.message, "warn", 3200); }
  });
  els.writingDictSearchBtn.addEventListener("click", async function () {
    var q = String(els.writingDictQuery.value || "").trim();
    if (!q) return;
    saveModuleSnapshot("writing");
    if (state.isNativeDetached) {
      saveJson(STORAGE_KEYS.dictSnapshot, { query: q, exact: Boolean(els.writingDictExact.checked) });
      try {
        await callApi("detach_native_window", "dictionary",
          Math.round(window.screenX + 60), Math.round(window.screenY + 60));
      } catch (err) { toast("打开词典窗口失败：" + err.message, "warn", 3200); }
      return;
    }
    state.activeDocked = "dictionary";
    renderDockPanels(); updateTabVisualState();
    els.dictQuery.value = q;
    els.dictExact.checked = Boolean(els.writingDictExact.checked);
    await runDictionarySearch(q, els.writingDictExact.checked);
  });
}

function bindAppSettingsEvents() {
  els.checkUpdateBtn.addEventListener("click", async function () {
    els.checkUpdateBtn.disabled = true;
    els.checkUpdateBtn.textContent = "检查中...";
    els.updateCheckStatus.textContent = "正在检查更新...";
    els.forceDownloadBtn.classList.add("hidden");
    try {
      var ret = await callApi("app_check_for_update");
      toast(ret?.message || "操作完成", ret?.ok ? "info" : "warn", 5000);
      var fresh = await callApi("app_get_settings");
      applyAppSettings(fresh);
    } catch (err) {
      toast("检查失败：" + err.message, "warn", 5000);
      if (els.updateCheckStatus) els.updateCheckStatus.textContent = "就绪";
    } finally {
      els.checkUpdateBtn.disabled = false;
      els.checkUpdateBtn.textContent = "检查更新";
    }
  });
  els.alicFontToggle.addEventListener("change", async function () {
    var n = Boolean(els.alicFontToggle.checked);
    try {
      var ret = await callApi("app_save_settings", { alic_font: n });
      applyAppSettings(ret?.settings || { alic_font: n });
      toast("字体设置已保存。", "info");
    } catch (err) {
      els.alicFontToggle.checked = state.settings.alicFont;
      toast("保存设置失败：" + err.message, "warn", 3200);
    }
  });
  els.alicHoverToggle.addEventListener("change", async function () {
    var n = Boolean(els.alicHoverToggle.checked);
    try {
      var ret = await callApi("app_save_settings", { alic_hover_enabled: n });
      applyAppSettings(ret?.settings || { alic_hover_enabled: n });
    } catch (err) {
      els.alicHoverToggle.checked = state.settings.alicHoverEnabled;
      toast("保存设置失败：" + err.message, "warn", 3200);
    }
  });
  els.alicHoverDelaySlider.addEventListener("input", function () {
    var v = Number(els.alicHoverDelaySlider.value) || 0;
    state.settings.alicHoverDelay = v;
    els.alicHoverDelayLabel.textContent = v + " ms";
  });
  els.alicHoverDelaySlider.addEventListener("change", async function () {
    var v = Number(els.alicHoverDelaySlider.value) || 0;
    try {
      var ret = await callApi("app_save_settings", { alic_hover_delay: v });
      applyAppSettings(ret?.settings || { alic_hover_delay: v });
    } catch (err) {
      els.alicHoverDelaySlider.value = state.settings.alicHoverDelay;
      toast("保存设置失败：" + err.message, "warn", 3200);
    }
  });

  els.dataDirBrowseBtn.addEventListener("click", async function () {
    els.dataDirBrowseBtn.disabled = true;
    try {
      var ret = await callApi("app_select_data_dir");
      if (ret?.ok) {
        els.dataDirInput.value = ret.path;
        state.settings.dataDir = ret.path;
        if (els.dataDirNote) els.dataDirNote.textContent = "已设置，文件已自动迁移";
        toast(ret.message, "info", 4000);
      } else if (ret?.message) {
        toast(ret.message, "info");
      }
    } catch (err) {
      toast("选择目录失败：" + err.message, "warn", 3200);
    } finally {
      els.dataDirBrowseBtn.disabled = false;
    }
  });

  els.dataDirOpenBtn.addEventListener("click", async function () {
    els.dataDirOpenBtn.disabled = true;
    try {
      var ret = await callApi("app_open_data_dir");
      if (ret?.message) toast(ret.message, ret?.ok ? "info" : "warn");
    } catch (err) {
      toast("打开失败：" + err.message, "warn", 3200);
    } finally {
      els.dataDirOpenBtn.disabled = false;
    }
  });

  setInterval(async function () {
    try {
      var ret = await callApi("app_get_settings");
      if (els.updateCheckStatus) {
        els.updateCheckStatus.textContent = String(ret?.update_check_status || "就绪");
      }
      if (els.forceDownloadBtn) {
        var showBtn = String(ret?.update_check_status || "") === "云端版本未变化，无需下载";
        els.forceDownloadBtn.classList.toggle("hidden", !showBtn);
      }
    } catch (_) {}
  }, 3000);

  els.forceDownloadBtn.addEventListener("click", async function () {
    els.forceDownloadBtn.disabled = true;
    els.forceDownloadBtn.textContent = "下载中...";
    els.updateCheckStatus.textContent = "正在下载...";
    try {
      var ret = await callApi("app_force_download_update");
      toast(ret?.message || "操作完成", ret?.ok ? "info" : "warn", 5000);
      if (els.updateCheckStatus) {
        var fresh = await callApi("app_get_settings");
        els.updateCheckStatus.textContent = String(fresh?.update_check_status || "就绪");
        var showBtn = String(fresh?.update_check_status || "") === "云端版本未变化，无需下载";
        els.forceDownloadBtn.classList.toggle("hidden", !showBtn);
      }
    } catch (err) {
      toast("操作失败：" + err.message, "warn", 5000);
      if (els.updateCheckStatus) els.updateCheckStatus.textContent = "就绪";
      els.forceDownloadBtn.classList.add("hidden");
    } finally {
      els.forceDownloadBtn.disabled = false;
      els.forceDownloadBtn.textContent = "仍然下载";
    }
  });
}
