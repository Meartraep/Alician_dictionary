import sqlite3
import sys
import os
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Any

MAX_ROW_DETAILS = 2000


def _truncate(val, max_len=60):
    s = str(val or "")
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


def _build_diff(local_path: str, remote_path: str) -> Dict[str, Any]:
    diffs: Dict[str, Any] = {
        "tables": {},
        "total_added": 0,
        "total_removed": 0,
        "total_modified": 0,
        "total_field_changes": 0,
    }

    remote_conn = sqlite3.connect(remote_path)
    rc = remote_conn.cursor()
    rc.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    remote_tables = {r[0] for r in rc.fetchall()}

    if os.path.exists(local_path):
        local_conn = sqlite3.connect(local_path)
        lc = local_conn.cursor()
        lc.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        local_tables = {r[0] for r in lc.fetchall()}
    else:
        local_conn = None
        local_tables = set()

    all_tables = sorted(remote_tables | local_tables)

    for table in all_tables:
        table_diff: Dict[str, Any] = {
            "remote_rows": 0,
            "local_rows": 0,
            "added": 0,
            "removed": 0,
            "modified": 0,
            "field_changes": 0,
            "view_added": [],
            "view_removed": [],
            "field_diffs": [],
            "truncated_added": False,
            "truncated_removed": False,
            "truncated_modified": False,
        }

        rc.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{table}'")
        if not rc.fetchone()[0]:
            table_diff["remote_rows"] = 0
        else:
            rc.execute(f"SELECT COUNT(*) FROM \"{table}\"")
            table_diff["remote_rows"] = rc.fetchone()[0]

        if local_conn and table in local_tables:
            lc.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{table}'")
            if lc.fetchone()[0]:
                lc.execute(f"SELECT COUNT(*) FROM \"{table}\"")
                table_diff["local_rows"] = lc.fetchone()[0]
        else:
            table_diff["local_rows"] = 0

        if table_diff["remote_rows"] == 0 and table_diff["local_rows"] == 0:
            diffs["tables"][table] = table_diff
            continue

        rc.execute(f'PRAGMA table_info("{table}")')
        remote_cols = [col[1] for col in rc.fetchall()]
        local_cols = remote_cols[:]
        if local_conn and table in local_tables:
            lc.execute(f'PRAGMA table_info("{table}")')
            local_cols = [col[1] for col in lc.fetchall()]

        common_cols = [c for c in remote_cols if c in local_cols]
        has_id = "id" in common_cols
        id_col = "id" if has_id else "rowid"

        if table_diff["local_rows"] == 0:
            table_diff["added"] = table_diff["remote_rows"]
            diffs["total_added"] += table_diff["added"]
            if table_diff["added"] <= MAX_ROW_DETAILS:
                rc.execute(f'SELECT {id_col}, * FROM "{table}"')
                cols = [d[0] for d in rc.description]
                for row in rc.fetchall():
                    table_diff["view_added"].append({cols[i]: row[i] for i in range(len(cols))})
            else:
                rc.execute(f'SELECT {id_col}, * FROM "{table}" LIMIT {MAX_ROW_DETAILS}')
                cols = [d[0] for d in rc.description]
                for row in rc.fetchall():
                    table_diff["view_added"].append({cols[i]: row[i] for i in range(len(cols))})
                table_diff["truncated_added"] = True
            diffs["tables"][table] = table_diff
            continue

        if table_diff["remote_rows"] == 0:
            table_diff["removed"] = table_diff["local_rows"]
            diffs["total_removed"] += table_diff["removed"]
            diffs["tables"][table] = table_diff
            continue

        if not common_cols:
            table_diff["added"] = table_diff["remote_rows"]
            table_diff["removed"] = table_diff["local_rows"]
            diffs["total_added"] += table_diff["added"]
            diffs["total_removed"] += table_diff["removed"]
            diffs["tables"][table] = table_diff
            continue

        cols_str = ", ".join(f'"{c}"' for c in common_cols)

        rc.execute(f"SELECT {id_col}, {cols_str} FROM \"{table}\"")
        remote_raw = rc.fetchall()
        lc.execute(f"SELECT {id_col}, {cols_str} FROM \"{table}\"")
        local_raw = lc.fetchall()

        remote_rows = {row[0]: row for row in remote_raw}
        local_rows = {row[0]: row for row in local_raw}

        remote_ids_set = set(remote_rows.keys())
        local_ids_set = set(local_rows.keys())

        added_ids = remote_ids_set - local_ids_set
        removed_ids = local_ids_set - remote_ids_set
        common_ids = remote_ids_set & local_ids_set

        table_diff["added"] = len(added_ids)
        table_diff["removed"] = len(removed_ids)

        added_sample_count = 0
        for rid in added_ids:
            if added_sample_count >= MAX_ROW_DETAILS:
                table_diff["truncated_added"] = True
                break
            row_dict = dict(zip(common_cols, remote_rows[rid][1:]))
            row_dict[id_col] = rid
            table_diff["view_added"].append(row_dict)
            added_sample_count += 1

        removed_sample_count = 0
        for rid in removed_ids:
            if removed_sample_count >= MAX_ROW_DETAILS:
                table_diff["truncated_removed"] = True
                break
            row_dict = dict(zip(common_cols, local_rows[rid][1:]))
            row_dict[id_col] = rid
            table_diff["view_removed"].append(row_dict)
            removed_sample_count += 1

        field_change_count = 0
        modified_count = 0
        for rid in common_ids:
            remote_vals = remote_rows[rid]
            local_vals = local_rows[rid]
            rdict = dict(zip(common_cols, remote_vals[1:]))
            ldict = dict(zip(common_cols, local_vals[1:]))
            row_changed = False
            for col in common_cols:
                rv = rdict.get(col)
                lv = ldict.get(col)
                if str(lv) != str(rv):
                    row_changed = True
                    field_change_count += 1
                    if field_change_count <= MAX_ROW_DETAILS:
                        table_diff["field_diffs"].append({
                            "row_id": rid,
                            "col": col,
                            "local_val": _truncate(lv, 120),
                            "remote_val": _truncate(rv, 120),
                        })
            if row_changed:
                modified_count += 1

        table_diff["modified"] = modified_count
        table_diff["field_changes"] = field_change_count
        if field_change_count > MAX_ROW_DETAILS:
            table_diff["truncated_modified"] = True

        diffs["total_added"] += table_diff["added"]
        diffs["total_removed"] += table_diff["removed"]
        diffs["total_modified"] += table_diff["modified"]
        diffs["total_field_changes"] += field_change_count
        diffs["tables"][table] = table_diff

    remote_conn.close()
    if local_conn:
        local_conn.close()
    return diffs


def _show_diff_window(diffs: Dict[str, Any]) -> bool:
    root = tk.Tk()
    root.title("数据库更新 — 差异对比")
    root.geometry("1020x720")
    root.resizable(True, True)
    root.protocol("WM_DELETE_WINDOW", lambda: _on_decide(root, False))

    result = {"accepted": False}

    def _on_decide(r, accepted):
        result["accepted"] = accepted
        r.quit()
        r.destroy()

    summary_frame = ttk.LabelFrame(root, text="差异摘要", padding="10")
    summary_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

    changed_tables = [t for t, d in diffs["tables"].items()
                      if d["added"] or d["removed"] or d["modified"]]

    summary_text = (
        f"新增行: {diffs['total_added']:,}    删除行: {diffs['total_removed']:,}    "
        f"修改行: {diffs['total_modified']:,}    字段变更: {diffs['total_field_changes']:,}    "
        f"涉及表: {len(changed_tables)}"
    )
    ttk.Label(summary_frame, text=summary_text, font=("Segoe UI", 11)).pack(anchor=tk.W)

    paned = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
    paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))

    left_frame = ttk.LabelFrame(paned, text="表概览 (双击查看详情)", padding="6")
    paned.add(left_frame, weight=3)

    table_cols = ("table", "added", "removed", "modified", "changes", "local", "remote")
    tree = ttk.Treeview(left_frame, columns=table_cols, show="headings", selectmode="browse")
    tree.heading("table", text="表名")
    tree.heading("added", text="新增")
    tree.heading("removed", text="删除")
    tree.heading("modified", text="修改")
    tree.heading("changes", text="字段变更")
    tree.heading("local", text="本地")
    tree.heading("remote", text="云端")
    tree.column("table", width=120)
    tree.column("added", width=50, anchor=tk.CENTER)
    tree.column("removed", width=50, anchor=tk.CENTER)
    tree.column("modified", width=50, anchor=tk.CENTER)
    tree.column("changes", width=60, anchor=tk.CENTER)
    tree.column("local", width=50, anchor=tk.CENTER)
    tree.column("remote", width=50, anchor=tk.CENTER)

    l_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=l_scroll.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    l_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    for table, d in sorted(diffs["tables"].items()):
        if d["added"] or d["removed"] or d["modified"]:
            tree.insert("", tk.END, values=(
                table, d["added"], d["removed"], d["modified"],
                d["field_changes"], d["local_rows"], d["remote_rows"]))

    tree.tag_configure("added_tag", background="#d4edda")
    tree.tag_configure("removed_tag", background="#f8d7da")
    tree.tag_configure("modified_tag", background="#fff3cd")
    tree.tag_configure("mixed_tag", background="#e8daef")
    for item in tree.get_children():
        vals = tree.item(item, "values")
        a, r, m = int(vals[1]), int(vals[2]), int(vals[3])
        if a > 0 and m > 0:
            tree.item(item, tags=("mixed_tag",))
        elif a > 0:
            tree.item(item, tags=("added_tag",))
        elif r > 0:
            tree.item(item, tags=("removed_tag",))
        elif m > 0:
            tree.item(item, tags=("modified_tag",))

    right_frame = ttk.LabelFrame(paned, text="逐字段差异", padding="6")
    paned.add(right_frame, weight=5)

    detail_text = tk.Text(right_frame, wrap=tk.WORD, font=("Consolas", 10),
                          state=tk.DISABLED, borderwidth=1, relief=tk.SOLID)
    detail_text.configure(bg="#fafbfc")
    d_scroll = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=detail_text.yview)
    detail_text.configure(yscrollcommand=d_scroll.set)
    detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    d_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    status_var = tk.StringVar(value="双击左侧表名查看逐字段差异详情")

    def _show_detail(table_name):
        d = diffs["tables"].get(table_name)
        if not d:
            return

        detail_text.configure(state=tk.NORMAL)
        detail_text.delete("1.0", tk.END)

        parts = []
        parts.append(f"══════ 表: {table_name} ══════\n")
        parts.append(f"本地 {d['local_rows']:,} 行  →  云端 {d['remote_rows']:,} 行")
        parts.append(f"    新增 {d['added']:,}  删除 {d['removed']:,}  修改 {d['modified']:,}  字段变更 {d['field_changes']:,}\n")

        added_rows = d.get("view_added") or []
        if added_rows:
            parts.append(f"── 新增行 (显示 {len(added_rows)}{'/' + str(d['added']) if d.get('truncated_added') else ''}) ──")
            first_row = added_rows[0] if added_rows else {}
            cols = list(first_row.keys())
            for row in added_rows:
                parts.append(f"  + 行 {row.get('id', row.get('rowid', '?'))}:")
                for c in cols:
                    if c in ("id", "rowid"):
                        continue
                    parts.append(f"       {c}: {_truncate(row.get(c, ''), 80)}")
            parts.append("")

        removed_rows = d.get("view_removed") or []
        if removed_rows:
            parts.append(f"── 删除行 (显示 {len(removed_rows)}{'/' + str(d['removed']) if d.get('truncated_removed') else ''}) ──")
            first_row = removed_rows[0] if removed_rows else {}
            cols = list(first_row.keys())
            for row in removed_rows:
                parts.append(f"  - 行 {row.get('id', row.get('rowid', '?'))}:")
                for c in cols:
                    if c in ("id", "rowid"):
                        continue
                    parts.append(f"       {c}: {_truncate(row.get(c, ''), 80)}")
            parts.append("")

        field_diffs = d.get("field_diffs") or []
        if field_diffs:
            parts.append(f"── 修改详情 (显示 {min(len(field_diffs), d['field_changes'])}{'/' + str(d['field_changes']) if d.get('truncated_modified') else ''}) ──")
            for fd in field_diffs:
                parts.append(
                    f"  ~ 行 {fd['row_id']}  [{fd['col']}]\n"
                    f"     本地: {fd['local_val']}\n"
                    f"     云端: {fd['remote_val']}\n"
                )

        if (not added_rows) and (not removed_rows) and (not field_diffs):
            parts.append("(无详细变更数据)")

        detail_text.insert("1.0", "\n".join(parts))
        detail_text.configure(state=tk.DISABLED)

        status_var.set(f"表 {table_name}: 新增 {d['added']}  删除 {d['removed']}  修改 {d['modified']}  字段变更{d['field_changes']}")

    tree.bind("<Double-1>", lambda e: (
        _show_detail(tree.item(tree.selection()[0], "values")[0])
        if tree.selection() else None
    ))

    tree.bind("<Return>", lambda e: (
        _show_detail(tree.item(tree.selection()[0], "values")[0])
        if tree.selection() else None
    ))

    if changed_tables:
        first_item = tree.get_children()[0]
        tree.selection_set(first_item)
        _show_detail(tree.item(first_item, "values")[0])

    btn_frame = ttk.Frame(root)
    btn_frame.pack(fill=tk.X, padx=10, pady=8)

    ttk.Label(btn_frame, textvariable=status_var, font=("Segoe UI", 9)).pack(side=tk.LEFT)
    ttk.Button(btn_frame, text="采纳更新 (覆盖本地数据库)",
               command=lambda: _on_decide(root, True)).pack(side=tk.RIGHT, padx=5)
    ttk.Button(btn_frame, text="放弃更新",
               command=lambda: _on_decide(root, False)).pack(side=tk.RIGHT, padx=5)

    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")
    root.lift()

    root.mainloop()
    return result["accepted"]


def main():
    if len(sys.argv) < 3:
        print("Usage: db_update_dialog.py <local_db_path> <remote_temp_path>", file=sys.stderr)
        sys.exit(1)

    local_path = sys.argv[1]
    remote_temp_path = sys.argv[2]

    diffs = _build_diff(local_path, remote_temp_path)

    accepted = _show_diff_window(diffs)

    if accepted:
        with open(remote_temp_path, "rb") as src:
            with open(local_path, "wb") as dst:
                dst.write(src.read())
        print("ACCEPTED", flush=True)
    else:
        print("REJECTED", flush=True)

    try:
        os.remove(remote_temp_path)
    except Exception:
        pass


if __name__ == "__main__":
    main()
