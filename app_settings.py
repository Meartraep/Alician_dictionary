from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict


class AppSettings:
    def __init__(self, settings_path: Path, db_path: Path) -> None:
        self.settings_path = Path(settings_path)
        self.db_path = Path(db_path)
        self.default_settings: Dict[str, Any] = {
            "auto_update": True,
            "known_db_sha1": "",
            "auto_update_status": "",
            "remote_db_sha1": "",
            "alic_font": False,
            "alic_hover_enabled": True,
            "alic_hover_delay": 300,
            "update_check_status": "就绪",
        }
        self.settings = self._load()
        self.detect_local_db_change()

    def _load(self) -> Dict[str, Any]:
        if not self.settings_path.exists():
            return self.default_settings.copy()
        try:
            with self.settings_path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            data = self.default_settings.copy()
            if isinstance(loaded, dict):
                for key in data:
                    if key in loaded:
                        data[key] = loaded[key]
            return data
        except Exception:
            return self.default_settings.copy()

    def save(self) -> bool:
        try:
            with self.settings_path.open("w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def current_db_sha1(self) -> str:
        if not self.db_path.exists():
            return ""
        digest = hashlib.sha1()
        with self.db_path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def detect_local_db_change(self) -> bool:
        current_sha = self.current_db_sha1()
        known_sha = str(self.settings.get("known_db_sha1") or "")
        if not current_sha:
            self.settings["auto_update_status"] = "未找到数据库文件。"
            return False

        if not known_sha:
            self.settings["known_db_sha1"] = current_sha
            self.settings["auto_update_status"] = "自动更新开启。"
            self.save()
            return False

        if self.settings.get("auto_update", True) and known_sha != current_sha:
            self.settings["auto_update"] = False
            self.settings["auto_update_status"] = "检测到本地数据库已更改，已自动关闭自动更新。"
            self.save()
            return True

        self.settings["auto_update_status"] = "自动更新开启。" if self.settings.get("auto_update", True) else "自动更新关闭。"
        return False

    def get_public_settings(self) -> Dict[str, Any]:
        self.detect_local_db_change()
        return {
            "auto_update": bool(self.settings.get("auto_update", True)),
            "auto_update_status": str(self.settings.get("auto_update_status") or ""),
            "alic_font": bool(self.settings.get("alic_font", False)),
            "alic_hover_enabled": bool(self.settings.get("alic_hover_enabled", True)),
            "alic_hover_delay": int(self.settings.get("alic_hover_delay", 300)),
            "update_check_status": str(self.settings.get("update_check_status") or "就绪"),
        }

    def set_auto_update(self, enabled: bool) -> Dict[str, Any]:
        self.settings["auto_update"] = bool(enabled)
        if enabled:
            self.settings["known_db_sha1"] = self.current_db_sha1()
            self.settings["auto_update_status"] = "自动更新开启。"
        else:
            self.settings["auto_update_status"] = "自动更新关闭。"
        self.save()
        return self.get_public_settings()

    def mark_database_updated_by_app(self) -> None:
        self.settings["known_db_sha1"] = self.current_db_sha1()
        self.settings["auto_update_status"] = "自动更新开启。" if self.settings.get("auto_update", True) else "自动更新关闭。"
        self.save()

    def mark_local_database_changed(self) -> None:
        if self.settings.get("auto_update", True):
            self.settings["auto_update"] = False
            self.settings["auto_update_status"] = "检测到本地数据库已更改，已自动关闭自动更新。"
            self.save()

    def set_update_check_status(self, status: str) -> None:
        self.settings["update_check_status"] = status
        self.save()
