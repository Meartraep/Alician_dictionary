function _stripColonsFromAlicFont(text) {
  var source = String(text || "");
  var lines = source.split("\n");
  var out = [];
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i];
    var ci = line.indexOf("：");
    if (ci < 0) ci = line.indexOf(":");
    if (ci >= 0) {
      out.push(line.slice(0, ci + 1) + '<span class="no-alic-font">' + line.slice(ci + 1) + '</span>');
    } else {
      out.push(line);
    }
  }
  return out.join("\n");
}

function applyWordHighlight(text, word) {
  var source = String(text || ""), target = String(word || "").trim();
  if (!target) return escapeHtml(source);
  var regex = new RegExp("\\b" + escapeRegExp(target) + "\\b", "gi");
  var output = "", last = 0, match = regex.exec(source);
  while (match) {
    output += escapeHtml(source.slice(last, match.index));
    output += '<mark class="lyric-word-hit">' + escapeHtml(match[0]) + '</mark>';
    last = match.index + match[0].length;
    match = regex.exec(source);
  }
  output += escapeHtml(source.slice(last));
  return output;
}

function renderLyricWithFocus(lyric, word, start, end) {
  var full = String(lyric || "");
  var s = clamp(Number(start || 0), 0, full.length);
  var e = clamp(Number(end || 0), s, full.length);
  var before = full.slice(0, s), focused = full.slice(s, e), after = full.slice(e);
  var focusHtml = focused
    ? '<span class="lyric-paragraph-focus">' + applyWordHighlight(focused, word) + '</span>'
    : "";
  var raw = applyWordHighlight(before, word) + focusHtml + applyWordHighlight(after, word);
  return _stripColonsFromAlicFont(raw);
}

async function runDictionarySearch(query, exactMatch, positionFilter) {
  var q = String(query ?? els.dictQuery.value).trim();
  if (!q) return toast("请输入要查询的词。", "warn");
  var exact = Boolean(exactMatch ?? els.dictExact.checked);
  var position = String(positionFilter ?? (els.dictPositionFilter.value || "any"));
  saveJson(STORAGE_KEYS.dictSnapshot, { query: q, exact: exact, position: position });
  try {
    var ret = await callApi("dictionary_search", q, exact, position);
    renderDictionaryResults(ret);
  } catch (err) { toast("查询失败：" + err.message, "warn", 3200); }
}

function renderDictionaryHistory(history) {
  var list = Array.isArray(history) ? history : [];
  if (!list.length) {
    els.dictHistory.innerHTML = '<div class="history-item">暂无历史记录</div>';
    return;
  }
  els.dictHistory.innerHTML = list.map(function (item) {
    return '<div class="history-item" data-query="' + escapeHtml(item) + '">' + escapeHtml(item) + '</div>';
  }).join("");
}

function renderDictionaryResults(payload) {
  var sections = payload?.sections || [];
  if (!sections.length) {
    var html = '<div class="result-item">' +
      escapeHtml(payload?.message || "未找到结果") + '</div>';
    html += renderDictionarySuggestions(payload?.suggestions);
    els.dictResults.innerHTML = html;
    if (payload?.context_examples) {
      state.dictionary.currentExamplesPayload = payload.context_examples;
      renderDictionaryExamples(payload.context_examples);
    }
    renderDictionaryHistory(payload?.history || []);
    return;
  }
  els.dictResults.innerHTML = sections.map(function (sec) {
    var rows = (sec.entries || []).map(function (entry) {
      return '<div class="result-item">' +
        '<div class="result-main">' + escapeHtml(entry.word || "") + '</div>' +
        '<div class="result-meta"><span class="no-alic-font">' +
        (entry.word_class || "词类未知") + ' | 词频: ' + (entry.count ?? 0) +
        ' | 泛度: ' + (entry.variety ?? 0) + '</span></div>' +
        '<div class="example-paragraph"><span class="no-alic-font">' + escapeHtml(entry.explanation || "") + '</span></div>' +
        '<div class="result-actions">' +
        '<button class="small dict-example-btn" type="button" data-word="' +
        escapeHtml(entry.word || "") + '">显示例句</button></div></div>';
    }).join("");
    return '<section class="result-section">' +
      '<div class="result-section-title">' + escapeHtml(sec.title || "") + '</div>' +
      rows + '</section>';
  }).join("") + renderDictionarySuggestions(payload?.suggestions);
  if (payload?.context_examples?.examples?.length) {
    state.dictionary.currentExamplesPayload = payload.context_examples;
    renderDictionaryExamples(payload.context_examples);
  }
  renderDictionaryHistory(payload?.history || []);
}

function renderDictionarySuggestions(suggestions) {
  if (!suggestions || !suggestions.length) return "";
  return '<section class="result-section">' +
    '<div class="result-section-title">词义相似词推荐</div>' +
    suggestions.map(function (item) {
      var wordLinks = (item.words || []).map(function (w) {
        return '<span class="suggestion-word-link" data-query="' +
          escapeHtml(w) + '" title="点击搜索此词">' + escapeHtml(w) + '</span>';
      }).join(" ");
      return '<div class="result-item suggestion-item">' +
        '<div class="result-main"><span class="no-alic-font">' +
        escapeHtml(item.explanation || "") + '</span></div>' +
        '<div class="result-meta">相似度: ' + (item.similarity != null ?
          (item.similarity * 100).toFixed(1) + '%' : 'N/A') + '</div>' +
        '<div class="result-meta">对应爱丽丝语: ' + wordLinks + '</div>' +
        '</div>';
    }).join("") + '</section>';
}

async function loadDictionaryExamples(word) {
  var target = String(word || "").trim();
  if (!target) return;
  try {
    var ret = await callApi("dictionary_examples", target, els.dictPositionFilter.value || "any");
    state.dictionary.currentExamplesPayload = ret;
    renderDictionaryExamples(ret);
  } catch (err) { toast("加载例句失败：" + err.message, "warn", 3200); }
}

function renderDictionaryExamples(payload) {
  var examples = payload?.examples || [];
  if (!examples.length) {
    els.dictExamples.innerHTML = '<div class="example-item">' +
      escapeHtml(payload?.message || "无例句") + '</div>';
    return;
  }
  var word = payload.word || "";
  els.dictExamples.innerHTML = examples.map(function (ex, idx) {
    return '<div class="example-item">' +
      '<div class="example-source"><span class="no-alic-font">' + escapeHtml(ex.album || "") + ' - ' +
      escapeHtml(ex.title || "") + '</span></div>' +
      '<div class="example-paragraph">' + _stripColonsFromAlicFont(applyWordHighlight(ex.paragraph || "", word)) + '</div>' +
      '<div class="result-actions">' +
      '<button class="small dict-context-btn" type="button" data-index="' + idx +
      '">查看上下文</button></div></div>';
  }).join("");
}

function openLyricContext(payload, sourceIndex) {
  var allExamples = payload?.examples || [];
  if (!allExamples.length || sourceIndex < 0 || sourceIndex >= allExamples.length) return;

  var currentIndex = sourceIndex;
  var originalTotal = Number(payload?.total_before || allExamples.length);
  var dedupRate = Number(payload?.deduplication_rate ?? 0);
  var songStats = Array.isArray(payload?.song_stats) ? payload.song_stats : [];

  showModal("例句上下文",
    '<div class="stats-box">' +
    '<div class="result-section-title">例句来源统计</div>' +
    '<div id="lyricStats"></div></div>' +
    '<div class="stats-box"><div id="lyricSongTitle">当前歌曲</div></div>' +
    '<div class="result-actions" style="margin-bottom:8px">' +
    '<button id="lyricPrevBtn" class="ghost" type="button">上一句</button>' +
    '<div id="lyricCounter" style="padding:7px 10px"></div>' +
    '<button id="lyricNextBtn" class="ghost" type="button">下一句</button>' +
    '<button id="lyricEditBtn" type="button" class="ghost">编辑歌词</button></div>' +
    '<div id="lyricView" class="lyric-view"></div>' +
    '<div class="result-actions">' +
    '<button id="lyricSaveBtn" type="button" class="hidden">保存歌词</button>' +
    '<button id="lyricCancelBtn" type="button" class="ghost hidden">取消编辑</button></div>' +
    '<div id="lyricEditWrap" class="hidden">' +
    '<div class="panel-subtitle">编辑模式：修改整首歌词后点击"保存歌词"</div>' +
    '<textarea id="lyricEditor" class="lyric-area"></textarea></div>',
    function () {
      var statsEl = document.getElementById("lyricStats");
      var titleEl = document.getElementById("lyricSongTitle");
      var counterEl = document.getElementById("lyricCounter");
      var viewEl = document.getElementById("lyricView");
      var editorEl = document.getElementById("lyricEditor");
      var editWrapEl = document.getElementById("lyricEditWrap");
      var prevBtn = document.getElementById("lyricPrevBtn");
      var nextBtn = document.getElementById("lyricNextBtn");
      var editBtn = document.getElementById("lyricEditBtn");
      var saveBtn = document.getElementById("lyricSaveBtn");
      var cancelBtn = document.getElementById("lyricCancelBtn");
      var editing = false;
      viewEl.tabIndex = 0;
      viewEl.addEventListener("click", function () { viewEl.focus(); });

      function renderStats() {
        var lines = [];
        lines.push("单词 '" + (payload.word || "") + "' 例句统计：");
        lines.push("• 总数量（查重前）：" + originalTotal + " 个");
        lines.push("• 总数量（查重后）：" + allExamples.length + " 个");
        lines.push("• 去重率：" + dedupRate.toFixed(1) + "%");
        lines.push("");
        lines.push("各歌曲例句分布（查重前/后）：");
        if (!songStats.length) { lines.push("• 无有效例句来源"); }
        else {
          for (var j = 0; j < songStats.length; j++) {
            var it = songStats[j];
            lines.push("• <span class=\"no-alic-font\">" + escapeHtml(it.album) + " - " +
              escapeHtml(it.title) + "</span>" +
              "：查重前 " + it.before + " 个，查重后 " + it.after + " 个");
          }
        }
        statsEl.innerHTML = lines.join("<br>");
      }

      function setEditMode(flag) {
        editing = Boolean(flag);
        editBtn.classList.toggle("hidden", editing);
        saveBtn.classList.toggle("hidden", !editing);
        cancelBtn.classList.toggle("hidden", !editing);
        viewEl.classList.toggle("hidden", editing);
        editWrapEl.classList.toggle("hidden", !editing);
        if (editing) {
          var viewHeight = viewEl.scrollHeight - viewEl.clientHeight;
          var ratio = viewHeight > 0 ? viewEl.scrollTop / viewHeight : 0;
          requestAnimationFrame(function () {
            editorEl.focus();
            var edHeight = editorEl.scrollHeight - editorEl.clientHeight;
            editorEl.scrollTop = edHeight > 0 ? ratio * edHeight : 0;
          });
        } else {
          requestAnimationFrame(function () { viewEl.focus(); });
        }
      }

      function renderAt() {
        var current = allExamples[currentIndex];
        if (!current) return;
        titleEl.innerHTML = "当前歌曲：<span class=\"no-alic-font\">" + escapeHtml(current.title) +
          " - " + escapeHtml(current.album) + "</span>";
        counterEl.textContent = "当前例句 " + (currentIndex + 1) + "/" +
          allExamples.length + "（原始例句总数：" + originalTotal + "）";
        viewEl.innerHTML = renderLyricWithFocus(current.lyric, payload.word, current.start, current.end);
        if (editing) editorEl.value = current.lyric || "";
        prevBtn.disabled = currentIndex <= 0;
        nextBtn.disabled = currentIndex >= allExamples.length - 1;
        var focus = viewEl.querySelector(".lyric-paragraph-focus");
        if (focus) focus.scrollIntoView({ block: "center", inline: "nearest" });
      }

      prevBtn.addEventListener("click", function () {
        if (currentIndex > 0) currentIndex -= 1; renderAt();
      });
      nextBtn.addEventListener("click", function () {
        if (currentIndex < allExamples.length - 1) currentIndex += 1; renderAt();
      });
      editBtn.addEventListener("click", function () {
        var c = allExamples[currentIndex];
        if (!c) return;
        editorEl.value = c.lyric || "";
        setEditMode(true);
      });
      cancelBtn.addEventListener("click", function () { setEditMode(false); });
      saveBtn.addEventListener("click", async function () {
        var c = allExamples[currentIndex];
        if (!c) return;
        try {
          var ret = await callApi("dictionary_update_lyric", c.title, c.album, editorEl.value || "");
          toast(ret?.message || "保存完成", ret?.ok ? "info" : "warn");
          if (ret?.ok) {
            await loadDictionaryExamples(payload.word);
            setEditMode(false); closeModal();
          }
        } catch (err) { toast("保存失败：" + err.message, "warn", 3200); }
      });
      renderStats(); setEditMode(false); renderAt();
    });
}

function bindDictionaryEvents() {
  els.dictSearchBtn.addEventListener("click", function () { runDictionarySearch(); });
  els.dictQuery.addEventListener("keydown", function (e) {
    if (e.key === "Enter") runDictionarySearch();
  });
  els.dictHistoryBtn.addEventListener("click", async function () {
    state.dictionary.historyVisible = !state.dictionary.historyVisible;
    if (state.dictionary.historyVisible && els.dictHistory.childElementCount === 0) {
      try { renderDictionaryHistory(await callApi("dictionary_history")); }
      catch (_) { renderDictionaryHistory([]); }
    }
    els.dictHistory.classList.toggle("hidden", !state.dictionary.historyVisible);
  });
  els.dictHistory.addEventListener("click", function (e) {
    var node = e.target.closest(".history-item[data-query]");
    if (!node) return;
    var query = node.dataset.query || "";
    els.dictQuery.value = query;
    state.dictionary.historyVisible = false;
    els.dictHistory.classList.add("hidden");
    runDictionarySearch(query);
  });
  els.dictResults.addEventListener("click", function (e) {
    var btn = e.target.closest(".dict-example-btn[data-word]");
    if (btn) {
      loadDictionaryExamples(btn.dataset.word || "");
      return;
    }
    var sugLink = e.target.closest(".suggestion-word-link[data-query]");
    if (sugLink) {
      var query = sugLink.dataset.query || "";
      els.dictQuery.value = query;
      runDictionarySearch(query);
    }
  });
  els.dictExamples.addEventListener("click", function (e) {
    var btn = e.target.closest(".dict-context-btn[data-index]");
    if (!btn || !state.dictionary.currentExamplesPayload) return;
    var idx = Number(btn.dataset.index);
    if (!Number.isInteger(idx)) return;
    openLyricContext(state.dictionary.currentExamplesPayload, idx);
  });
}

function getEditorText() {
  return (els.writingEditor.innerText || "").replace(/\r/g, "");
}

async function restoreModuleSnapshot(appId, shouldRunSearch) {
  shouldRunSearch = shouldRunSearch || false;
  if (appId === "dictionary") {
    var snapshot = loadJson(STORAGE_KEYS.dictSnapshot, {});
    if (typeof snapshot.query === "string") els.dictQuery.value = snapshot.query;
    els.dictExact.checked = Boolean(snapshot.exact);
    els.dictPositionFilter.value = snapshot.position || "any";
    if (shouldRunSearch && String(snapshot.query || "").trim()) {
      await runDictionarySearch(snapshot.query, Boolean(snapshot.exact), snapshot.position || "any");
    }
    return;
  }
  if (appId === "writing") {
    var snap = loadJson(STORAGE_KEYS.writingSnapshot, {});
    if (typeof snap.text === "string" && getEditorText() !== snap.text) {
      els.writingEditor.textContent = snap.text;
      state.writing.selectedSidebarKey = "";
      closeInfoPopup();
    }
    if (typeof snap.dictQuery === "string") els.writingDictQuery.value = snap.dictQuery;
    els.writingDictExact.checked = Boolean(snap.dictExact);
    if (shouldRunSearch) await runWritingCheck(true);
    return;
  }
  if (appId === "translator") {
    var trSnap = loadJson(STORAGE_KEYS.translatorSnapshot, {});
    if (typeof trSnap.direction === "string") {
      els.translatorDirection.value = trSnap.direction;
      state.translator.direction = trSnap.direction;
    }
    if (typeof trSnap.input === "string") els.translatorInput.value = trSnap.input;
    if (typeof trSnap.output === "string") els.translatorOutput.value = trSnap.output;
    state.translator.lastResult = trSnap.result || null;
    renderTranslatorResult(state.translator.lastResult);
  }
}
