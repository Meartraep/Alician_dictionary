from __future__ import annotations

import threading
from typing import Any, Dict, List


class DatabaseManagerService:
    def __init__(self, db_path: str) -> None:
        self._lock = threading.RLock()
        self._db_path = db_path
        from database_manager import DatabaseManager as DbManager

        self.db = DbManager()
        if not self.db.connect_database(db_path):
            raise RuntimeError(f"Failed to connect to database: {db_path}")

    def get_tables(self) -> List[str]:
        with self._lock:
            return [t for t in self.db.get_tables() if not t.startswith("sqlite_")]

    def get_fields(self, table_name: str) -> List[str]:
        with self._lock:
            return self.db.get_fields(str(table_name))

    def get_all_data(self, table_name: str) -> Dict[str, Any]:
        with self._lock:
            tn = str(table_name)
            fields = self.db.get_fields(tn)
            cursor = self.db.conn.cursor()
            if "id" in fields:
                cursor.execute(f'SELECT * FROM "{tn}" ORDER BY id')
            else:
                cursor.execute(f'SELECT rowid, * FROM "{tn}" ORDER BY rowid')
            rows = cursor.fetchall()
            if "id" not in fields:
                fields = ["rowid"] + fields
            return {"ok": True, "data": [dict(zip(fields, row)) for row in rows], "fields": fields, "table": tn}

    def search_records(self, table_name: str, keyword: str) -> Dict[str, Any]:
        with self._lock:
            tn, kw = str(table_name), str(keyword)
            if not kw:
                return self.get_all_data(tn)
            fields = self.db.get_fields(tn)
            if not fields:
                return {"ok": True, "data": [], "fields": fields, "table": tn}
            conditions = " OR ".join(f'"{f}" LIKE ?' for f in fields)
            params = tuple(f"%{kw}%" for _ in fields)
            cursor = self.db.conn.cursor()
            if "id" in fields:
                cursor.execute(f'SELECT * FROM "{tn}" WHERE {conditions}', params)
            else:
                cursor.execute(f'SELECT rowid, * FROM "{tn}" WHERE {conditions}', params)
            rows = cursor.fetchall()
            if "id" not in fields:
                fields = ["rowid"] + fields
            return {"ok": True, "data": [dict(zip(fields, row)) for row in rows], "fields": fields, "table": tn}

    def add_record(self, table_name: str, values: Dict[str, str]) -> Dict[str, Any]:
        with self._lock:
            tn = str(table_name)
            vals = {str(k): str(v) for k, v in (values or {}).items()}
            if not vals:
                return {"ok": False, "message": "没有可插入的数据。"}
            fields = self.db.get_fields(tn)
            insertable = {k: v for k, v in vals.items() if k in fields and k != "id"}
            if not insertable:
                return {"ok": False, "message": "没有匹配的字段。"}
            try:
                placeholders = ", ".join("?" for _ in insertable)
                cols = ", ".join(f'"{c}"' for c in insertable)
                self.db.conn.execute(
                    f'INSERT INTO "{tn}" ({cols}) VALUES ({placeholders})', tuple(insertable.values()))
                self.db.conn.commit()
                return {"ok": True, "message": "新增记录成功。"}
            except Exception as exc:
                return {"ok": False, "message": f"新增失败: {exc}"}

    def update_record(self, table_name: str, record_id: int, values: Dict[str, str]) -> Dict[str, Any]:
        with self._lock:
            tn = str(table_name)
            vals = {str(k): str(v) for k, v in (values or {}).items() if k not in ("id", "rowid")}
            if not vals:
                return {"ok": False, "message": "没有可更新的数据。"}
            try:
                setters = ", ".join(f'"{k}" = ?' for k in vals)
                fields = self.db.get_fields(tn)
                if "id" in fields:
                    params = tuple(vals.values()) + (int(record_id),)
                    self.db.conn.execute(f'UPDATE "{tn}" SET {setters} WHERE id = ?', params)
                else:
                    params = tuple(vals.values()) + (int(record_id),)
                    self.db.conn.execute(f'UPDATE "{tn}" SET {setters} WHERE rowid = ?', params)
                self.db.conn.commit()
                return {"ok": True, "message": "修改成功。"}
            except Exception as exc:
                return {"ok": False, "message": f"修改失败: {exc}"}

    def delete_records(self, table_name: str, ids: List[int]) -> Dict[str, Any]:
        with self._lock:
            tn = str(table_name)
            id_list = [int(i) for i in (ids or [])]
            if not id_list:
                return {"ok": False, "message": "请选择要删除的记录。"}
            try:
                placeholders = ", ".join("?" for _ in id_list)
                fields = self.db.get_fields(tn)
                if "id" in fields:
                    self.db.conn.execute(
                        f'DELETE FROM "{tn}" WHERE id IN ({placeholders})', tuple(id_list))
                else:
                    self.db.conn.execute(
                        f'DELETE FROM "{tn}" WHERE rowid IN ({placeholders})', tuple(id_list))
                self.db.conn.commit()
                self.db.conn.execute("VACUUM")
                return {"ok": True, "message": f"已删除 {len(id_list)} 条记录。"}
            except Exception as exc:
                return {"ok": False, "message": f"删除失败: {exc}"}

    def global_search(self, keyword: str) -> Dict[str, Any]:
        with self._lock:
            kw = str(keyword)
            if not kw:
                return {"ok": True, "results": []}
            results = self.db.global_search(kw)
            return {"ok": True, "results": results}

    def global_replace(self, keyword: str, replacement: str,
                       match_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        with self._lock:
            kw, rep, recs = str(keyword), str(replacement), match_records or []
            if not kw or not recs:
                return {"ok": False, "message": "缺少查找词或匹配记录。"}
            count, details = self.db.global_replace(kw, rep, recs)
            self.db.conn.execute("VACUUM")
            return {"ok": True, "replaced_count": count, "details": details}

    def close(self) -> None:
        with self._lock:
            self.db.close_connection()

    def batch_update(self, table_name: str, edits: List[Dict[str, Any]]) -> Dict[str, Any]:
        with self._lock:
            tn = str(table_name)
            if not edits:
                return {"ok": False, "message": "没有要提交的更改。"}
            count = 0
            try:
                for edit in edits:
                    rid = int(edit.get("id", 0))
                    vals = {str(k): str(v) for k, v in (edit.get("values") or {}).items()
                            if k not in ("id", "rowid")}
                    if not vals:
                        continue
                    setters = ", ".join(f'"{k}" = ?' for k in vals)
                    fields = self.db.get_fields(tn)
                    params = tuple(vals.values()) + (rid,)
                    if "id" in fields:
                        self.db.conn.execute(
                            f'UPDATE "{tn}" SET {setters} WHERE id = ?', params)
                    else:
                        self.db.conn.execute(
                            f'UPDATE "{tn}" SET {setters} WHERE rowid = ?', params)
                    count += 1
                self.db.conn.commit()
                self.db.conn.execute("VACUUM")
                return {"ok": True, "message": f"已提交 {count} 条更改。", "committed": count}
            except Exception as exc:
                try:
                    self.db.conn.rollback()
                except Exception:
                    pass
                return {"ok": False, "message": f"提交失败，已回滚: {exc}"}
