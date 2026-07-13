function renderDbmanagerTableList() {
  var list = els.dbmTableList;
  if (!list) return;
  list.innerHTML = state.dbmanager.tables.map(function (t) {
    var cls = t === state.dbmanager.currentTable ? "table-item active" : "table-item";
    return '<div class="' + cls + '" data-table="' + escapeHtml(t) + '">' + escapeHtml(t) + '</div>';
  }).join("");
  list.querySelectorAll(".table-item").forEach(function (el) {
    el.addEventListener("click", function () { loadDbmanagerTable(el.dataset.table); });
  });
}

function _dbmExitEditMode() {
  state.dbmanager.editingRowId = "";
  state.dbmanager.editedValues = {};
  els.dbmDiscardBtn.classList.add("hidden");
  els.dbmCommitBtn.classList.add("hidden");
}

async function loadDbmanagerTable(tableName) {
  _dbmExitEditMode();
  state.dbmanager.currentTable = tableName;
  state.dbmanager.selectedIds = new Set();
  state.dbmanager.dirtyRows = new Set();
  renderDbmanagerTableList();
  try {
    var ret = await callApi("dbmanager_get_all_data", tableName);
    if (ret?.ok) {
      state.dbmanager.fields = ret.fields || [];
      state.dbmanager.data = ret.data || [];
    } else {
      state.dbmanager.fields = []; state.dbmanager.data = [];
      toast(ret?.message || "加载失败", "warn");
    }
  } catch (err) {
    state.dbmanager.fields = []; state.dbmanager.data = [];
    toast("加载数据失败：" + err.message, "warn");
  }
  renderDbmanagerData();
}

function _dbmRowId(row) {
  if (row.id != null) return String(row.id);
  if (row.rowid != null) return String(row.rowid);
  return "";
}

function _dbmDrawTable(editRowId) {
  var fields = state.dbmanager.fields;
  var data = state.dbmanager.data;
  var wrap = els.dbmDataTable;
  if (!wrap) return;

  var html = '<table class="data-table"><thead><tr>';
  for (var i = 0; i < fields.length; i++) html += '<th>' + escapeHtml(fields[i]) + '</th>';
  html += '</tr></thead><tbody>';

  for (var i = 0; i < data.length; i++) {
    var row = data[i];
    var rowId = _dbmRowId(row);
    var selected = rowId && state.dbmanager.selectedIds.has(rowId);
    html += '<tr class="' + (selected ? 'selected' : '') + '" data-row-id="' + escapeHtml(rowId) + '">';
    for (var j = 0; j < fields.length; j++) {
      var f = fields[j];
      if (rowId === editRowId && f !== "id" && f !== "rowid") {
        var editVal = state.dbmanager.editedValues[f];
        if (editVal === undefined) editVal = String(row[f] ?? "");
        var isLong = (editVal.length > 40) || f === "explanation" || f === "lyric";
        if (isLong) {
          html += '<td><textarea class="dbm-inline-edit" data-field="' + escapeHtml(f) +
            '" rows="3">' + escapeHtml(editVal) + '</textarea></td>';
        } else {
          html += '<td><input class="dbm-inline-edit" data-field="' + escapeHtml(f) +
            '" type="text" value="' + escapeHtml(editVal) + '" /></td>';
        }
      } else {
        html += '<td title="' + escapeHtml(String(row[f] ?? '')) + '">' +
          escapeHtml(String(row[f] ?? '')) + '</td>';
      }
    }
    html += '</tr>';
  }
  html += '</tbody></table>';
  wrap.innerHTML = html;

  var rows = wrap.querySelectorAll("tbody tr");
  rows.forEach(function (tr) {
    tr.addEventListener("click", function (e) {
      if (e.target.tagName === "TEXTAREA") return;
      if (state.dbmanager.editingRowId) return;
      var rid = tr.dataset.rowId;
      if (!rid) return;
      state.dbmanager.selectedIds.clear();
      state.dbmanager.selectedIds.add(rid);
      syncDbmanagerRowSelection();
    });

    tr.addEventListener("dblclick", function (e) {
      if (state.dbmanager.editingRowId) return;
      var rid = tr.dataset.rowId;
      if (!rid) return;
      state.dbmanager.editingRowId = rid;
      state.dbmanager.editedValues = {};
      els.dbmDiscardBtn.classList.remove("hidden");
      els.dbmCommitBtn.classList.remove("hidden");
      renderDbmanagerData();
    });
  });
}

function renderDbmanagerData() {
  var fields = state.dbmanager.fields;
  var data = state.dbmanager.data;
  var wrap = els.dbmDataTable;
  if (!wrap) return;
  if (!fields.length) {
    wrap.innerHTML = '<div style="padding:20px;color:var(--muted)">请左侧选择数据表</div>';
    els.dbmStatus.textContent = "";
    return;
  }
  _dbmDrawTable(state.dbmanager.editingRowId);
  els.dbmStatus.textContent = "共 " + data.length + " 条记录";
}

function syncDbmanagerRowSelection() {
  var rows = els.dbmDataTable?.querySelectorAll("tbody tr");
  if (!rows) return;
  rows.forEach(function (tr) {
    var rid = tr.dataset.rowId;
    tr.classList.toggle("selected", Boolean(rid) && state.dbmanager.selectedIds.has(rid));
  });
}

function getDbmanagerSelectedIds() {
  return Array.from(state.dbmanager.selectedIds).map(Number).filter(function (n) { return !isNaN(n); });
}

function showDbmanagerDialog(title, fields, values, onSave) {
  var existing = document.querySelector(".dialog-overlay");
  if (existing) existing.remove();
  var overlay = document.createElement("div");
  overlay.className = "dialog-overlay";
  var fieldsHtml = "";
  for (var i = 0; i < fields.length; i++) {
    var f = fields[i];
    if (f === "id") continue;
    var val = escapeHtml(values[f] || "");
    var isLong = (values[f] && values[f].length > 40) || f === "explanation" || f === "lyric";
    var ih = isLong
      ? '<textarea id="dialog-f-' + escapeHtml(f) + '" rows="4">' + val + '</textarea>'
      : '<input id="dialog-f-' + escapeHtml(f) + '" type="text" value="' + val + '" />';
    fieldsHtml += '<div class="dialog-field"><label>' + escapeHtml(f) + '</label>' + ih + '</div>';
  }
  overlay.innerHTML = '<div class="dialog-card">' +
    '<div class="dialog-head"><h3>' + escapeHtml(title) +
    '</h3><button class="close-btn dialog-close-btn">&#x2715;</button></div>' +
    '<div class="dialog-body">' + fieldsHtml + '</div>' +
    '<div class="dialog-actions">' +
    '<button class="ghost dialog-cancel-btn">取消</button>' +
    '<button class="dialog-save-btn">保存</button></div></div>';
  document.body.appendChild(overlay);

  var close = function () { overlay.remove(); };
  overlay.querySelector(".dialog-close-btn").addEventListener("click", close);
  overlay.querySelector(".dialog-cancel-btn").addEventListener("click", close);
  overlay.addEventListener("click", function (e) { if (e.target === overlay) close(); });

  overlay.querySelector(".dialog-save-btn").addEventListener("click", function () {
    var result = {};
    for (var i = 0; i < fields.length; i++) {
      var f = fields[i];
      if (f === "id") continue;
      var el = overlay.querySelector("#dialog-f-" + CSS.escape(f));
      result[f] = el ? el.value : "";
    }
    onSave(result, close);
  });
  overlay.addEventListener("keydown", function (e) { if (e.key === "Escape") close(); });
}

async function dbmanagerRefresh() {
  if (!state.dbmanager.currentTable) { toast("请先选择数据表", "warn"); return; }
  await loadDbmanagerTable(state.dbmanager.currentTable);
  toast("已刷新", "info");
}

async function dbmanagerAddRecord() {
  var table = state.dbmanager.currentTable;
  if (!table) { toast("请先选择数据表", "warn"); return; }
  showDbmanagerDialog("新增记录 - " + table, state.dbmanager.fields, {}, async function (values, close) {
    try {
      var ret = await callApi("dbmanager_add_record", table, values);
      toast(ret?.message || "", ret?.ok ? "info" : "warn");
      if (ret?.ok) { close(); await loadDbmanagerTable(table); }
    } catch (err) { toast("新增失败：" + err.message, "warn"); }
  });
}

async function dbmanagerDiscardEdits() {
  _dbmExitEditMode();
  renderDbmanagerData();
  toast("已放弃更改", "info");
}

async function dbmanagerCommitEdits() {
  var table = state.dbmanager.currentTable;
  if (!table) return;
  var rowId = state.dbmanager.editingRowId;
  if (!rowId) { _dbmExitEditMode(); return; }

  var changed = {};
  var inlines = els.dbmDataTable?.querySelectorAll(".dbm-inline-edit");
  if (inlines) {
    inlines.forEach(function (el) {
      changed[el.dataset.field] = el.value || el.textContent || "";
    });
  }
  if (!Object.keys(changed).length) { _dbmExitEditMode(); renderDbmanagerData(); return; }

  try {
    var ret = await callApi("dbmanager_batch_update", table, [{ id: Number(rowId), values: changed }]);
    toast(ret?.message || "", ret?.ok ? "info" : "warn");
    if (ret?.ok) {
      _dbmExitEditMode();
      await loadDbmanagerTable(table);
    }
  } catch (err) { toast("提交失败：" + err.message, "warn"); }
}

async function dbmanagerDeleteRecords() {
  var ids = getDbmanagerSelectedIds();
  if (!ids.length) { toast("请选择要删除的记录", "warn"); return; }
  if (!confirm("确认删除 " + ids.length + " 条记录吗？此操作不可撤销。")) return;
  var table = state.dbmanager.currentTable;
  try {
    var ret = await callApi("dbmanager_delete_records", table, ids);
    toast(ret?.message || "", ret?.ok ? "info" : "warn");
    if (ret?.ok) await loadDbmanagerTable(table);
  } catch (err) { toast("删除失败：" + err.message, "warn"); }
}

async function dbmanagerSearch() {
  var table = state.dbmanager.currentTable;
  if (!table) { toast("请先选择数据表", "warn"); return; }
  var kw = (els.dbmSearchInput?.value || "").trim();
  var exact = Boolean(els.dbmSearchExact?.checked);
  try {
    var ret = await callApi("dbmanager_search", table, kw, exact);
    if (ret?.ok) {
      state.dbmanager.data = ret.data || [];
      state.dbmanager.selectedIds = new Set();
      renderDbmanagerData();
      els.dbmStatus.textContent = kw ? (exact ? "精确" : "模糊") + '搜索 "' + kw + '" — ' + ret.data.length + " 条结果" : "共 " + ret.data.length + " 条记录";
    } else { toast(ret?.message || "搜索失败", "warn"); }
  } catch (err) { toast("搜索失败：" + err.message, "warn"); }
}

async function dbmanagerShowAll() {
  var table = state.dbmanager.currentTable;
  if (!table) return;
  els.dbmSearchInput.value = "";
  await loadDbmanagerTable(table);
}

function renderGlobalResults() {
  var results = state.dbmanager.globalResults;
  if (!results || !results.length) { els.dbmGlobalStatus.textContent = "无结果"; return; }
  els.dbmGlobalStatus.textContent = "找到 " + results.length + " 条结果";
  var html = '<table class="global-results-table"><thead><tr>';
  html += '<th>表</th><th>ID</th><th>字段</th><th>值</th></tr></thead><tbody>';
  for (var i = 0; i < results.length; i++) {
    var r = results[i];
    var selected = state.dbmanager.globalSelectedIndexes.has(i);
    html += '<tr data-gidx="' + i + '" class="' + (selected ? 'selected' : '') + '">';
    html += '<td>' + escapeHtml(r.table || "") + '</td>';
    html += '<td>' + escapeHtml(String(r.id ?? "")) + '</td>';
    html += '<td>' + escapeHtml(r.field || "") + '</td>';
    html += '<td>' + escapeHtml(String(r.value ?? "")) + '</td></tr>';
  }
  html += '</tbody></table>';
  var container = document.getElementById("dbmGlobalResults");
  if (!container) {
    container = document.createElement("div");
    container.id = "dbmGlobalResults";
    container.className = "global-results card";
    container.style.cssText = "max-height:220px;overflow:auto;margin-top:8px;padding:8px";
    els.dbmGlobalStatus.parentElement.after(container);
  }
  container.innerHTML = html;
  var rows = container.querySelectorAll("tbody tr");
  rows.forEach(function (tr) {
    tr.addEventListener("click", function (e) {
      var idx = parseInt(tr.dataset.gidx, 10);
      if (isNaN(idx)) return;
      if (e.ctrlKey || e.metaKey) {
        if (state.dbmanager.globalSelectedIndexes.has(idx)) state.dbmanager.globalSelectedIndexes.delete(idx);
        else state.dbmanager.globalSelectedIndexes.add(idx);
      } else {
        state.dbmanager.globalSelectedIndexes.clear();
        state.dbmanager.globalSelectedIndexes.add(idx);
      }
      renderGlobalResults();
    });
    tr.addEventListener("dblclick", async function () {
      var idx = parseInt(tr.dataset.gidx, 10);
      var result = !isNaN(idx) ? state.dbmanager.globalResults[idx] : null;
      if (!result?.table) return;
      await loadDbmanagerTable(result.table);
      var targetId = result.id != null ? String(result.id) : "";
      if (targetId) {
        state.dbmanager.selectedIds.clear();
        state.dbmanager.selectedIds.add(targetId);
        syncDbmanagerRowSelection();
        var targetRow = els.dbmDataTable?.querySelector('tr[data-row-id="' + CSS.escape(targetId) + '"]');
        if (targetRow) targetRow.scrollIntoView({ block: "center" });
      }
    });
  });
}

async function dbmanagerGlobalSearch() {
  var kw = (els.dbmGlobalSearchInput?.value || "").trim();
  var exact = Boolean(els.dbmGlobalSearchExact?.checked);
  if (!kw) { toast("请输入搜索关键词", "warn"); return; }
  try {
    var ret = await callApi("dbmanager_global_search", kw, exact);
    if (ret?.ok) {
      state.dbmanager.globalResults = ret.results || [];
      state.dbmanager.globalSelectedIndexes = new Set();
      renderGlobalResults();
    }
  } catch (err) { toast("全局搜索失败：" + err.message, "warn"); }
}

function dbmanagerGlobalSelectAll() {
  if (!state.dbmanager.globalResults.length) {
    toast("请先执行全局搜索", "warn");
    return;
  }
  state.dbmanager.globalSelectedIndexes = new Set(
    state.dbmanager.globalResults.map(function (_, idx) { return idx; })
  );
  renderGlobalResults();
  toast("已全选搜索结果", "info");
}

function setDbmanagerGlobalSearchVisible(visible) {
  state.dbmanager.globalSearchVisible = Boolean(visible);
  els.dbmGlobalBar.classList.toggle("hidden", !state.dbmanager.globalSearchVisible);
  var results = document.getElementById("dbmGlobalResults");
  if (results) results.classList.toggle("hidden", !state.dbmanager.globalSearchVisible);
  els.dbmGlobalToggleBtn.textContent = state.dbmanager.globalSearchVisible
    ? "隐藏全局搜索" : "显示全局搜索";
}

async function dbmanagerGlobalReplace() {
  var kw = (els.dbmGlobalSearchInput?.value || "").trim();
  var rep = (els.dbmReplaceInput?.value || "").trim();
  if (!kw) { toast("请输入查找关键词", "warn"); return; }
  if (!rep) { toast("请输入替换内容", "warn"); return; }
  if (!state.dbmanager.globalResults.length) { toast("请先执行全局搜索", "warn"); return; }
  var matchRecords = Array.from(state.dbmanager.globalSelectedIndexes)
    .sort(function (a, b) { return a - b; })
    .map(function (idx) { return state.dbmanager.globalResults[idx]; })
    .filter(Boolean);
  if (!matchRecords.length) { toast("请勾选要替换的记录", "warn"); return; }
  if (!confirm('确认将 ' + matchRecords.length + ' 处 "' + kw + '" 替换为 "' + rep + '" 吗？此操作不可撤销。')) return;
  try {
    var ret = await callApi("dbmanager_global_replace", kw, rep, matchRecords);
    toast(ret?.message || "已替换 " + (ret?.replaced_count || 0) + " 处", ret?.ok ? "info" : "warn");
    if (ret?.ok) {
      await dbmanagerGlobalSearch();
      if (state.dbmanager.currentTable) await loadDbmanagerTable(state.dbmanager.currentTable);
    }
  } catch (err) { toast("替换失败：" + err.message, "warn"); }
}

async function dbmanagerLoadTables() {
  try {
    state.dbmanager.tables = await callApi("dbmanager_get_tables");
    if (state.dbmanager.tables.length && !state.dbmanager.currentTable) {
      state.dbmanager.currentTable = state.dbmanager.tables[0];
    }
    renderDbmanagerTableList();
    if (state.dbmanager.currentTable) await loadDbmanagerTable(state.dbmanager.currentTable);
  } catch (err) { toast("加载表列表失败：" + err.message, "warn"); }
}

function bindDbmanagerEvents() {
  if (!els.dbmRefreshBtn) return;
  els.dbmRefreshBtn.addEventListener("click", dbmanagerRefresh);
  els.dbmSearchBtn.addEventListener("click", dbmanagerSearch);
  els.dbmShowAllBtn.addEventListener("click", dbmanagerShowAll);
  els.dbmGlobalToggleBtn.addEventListener("click", function () {
    setDbmanagerGlobalSearchVisible(!state.dbmanager.globalSearchVisible);
  });
  els.dbmGlobalCloseBtn.addEventListener("click", function () {
    setDbmanagerGlobalSearchVisible(false);
  });
  els.dbmAddBtn.addEventListener("click", dbmanagerAddRecord);
  els.dbmDeleteBtn.addEventListener("click", dbmanagerDeleteRecords);
  els.dbmDiscardBtn.addEventListener("click", dbmanagerDiscardEdits);
  els.dbmCommitBtn.addEventListener("click", dbmanagerCommitEdits);
  els.dbmGlobalSearchBtn.addEventListener("click", dbmanagerGlobalSearch);
  els.dbmGlobalSelectAllBtn.addEventListener("click", dbmanagerGlobalSelectAll);
  els.dbmReplaceBtn.addEventListener("click", dbmanagerGlobalReplace);
  els.dbmUpdateWordCountBtn.addEventListener("click", async function () {
    try {
      var ret = await callApi("dbmanager_update_word_count");
      toast(ret?.message || "", ret?.ok ? "info" : "warn", 5000);
    } catch (err) { toast("更新失败：" + err.message, "warn", 5000); }
  });
  els.dbmClassifyWordsBtn.addEventListener("click", async function () {
    try {
      var ret = await callApi("dbmanager_classify_words");
      toast(ret?.message || "", ret?.ok ? "info" : "warn", 5000);
    } catch (err) { toast("更新失败：" + err.message, "warn", 5000); }
  });
  els.dbmExportCsvBtn.addEventListener("click", async function () {
    try {
      var ret = await callApi("dbmanager_export_csv");
      var message = ret?.message || "";
      if (ret?.ok && ret?.encoding) message += " 编码：" + ret.encoding;
      toast(message || "导出完成", ret?.ok ? "info" : "warn", 5000);
    } catch (err) { toast("导出失败：" + err.message, "warn", 5000); }
  });
  els.dbmExportDbBtn.addEventListener("click", async function () {
    try {
      var ret = await callApi("dbmanager_export_db");
      toast(ret?.message || "", ret?.ok ? "info" : "warn");
    } catch (err) { toast("启动失败：" + err.message, "warn"); }
  });
  els.dbmSearchInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") dbmanagerSearch();
  });
  els.dbmGlobalSearchInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") dbmanagerGlobalSearch();
  });
}
