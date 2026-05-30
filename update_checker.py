import hashlib
import os
import sys
import requests
import subprocess
import logging
import tempfile
from typing import Any, Dict


class UpdateChecker:
    def __init__(self, local_db_path, app_settings=None):
        self.local_db_path = local_db_path
        self.app_settings = app_settings
        self.github_repo = "Meartraep/Alician_dictionary"
        self.github_file_path = "translated.db"

        if getattr(sys, 'frozen', False):
            log_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            log_dir = os.path.dirname(os.path.abspath(__file__))
        log_file = os.path.join(log_dir, "update_checker.log")

        self.logger = logging.getLogger("UpdateChecker")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            handler.close()

        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except Exception as e:
            print(f"配置日志失败: {e}")

    def get_local_sha1(self):
        if not os.path.exists(self.local_db_path):
            return None
        sha1_hash = hashlib.sha1()
        with open(self.local_db_path, "rb") as f:
            while chunk := f.read(4096):
                sha1_hash.update(chunk)
        return sha1_hash.hexdigest()

    def get_remote_sha_safe(self):
        url1 = f"https://api.github.com/repos/{self.github_repo}/contents/{self.github_file_path}"
        url2 = f"https://mirror.ghproxy.com/https://api.github.com/repos/{self.github_repo}/contents/{self.github_file_path}"
        for url in [url1, url2]:
            try:
                response = requests.get(url, timeout=6)
                response.raise_for_status()
                data = response.json()
                sha_value = data.get("sha")
                self.logger.info(f"从{url}获取SHA值成功: {sha_value}")
                return sha_value
            except Exception as e:
                self.logger.error(f"从{url}获取SHA值失败: {e}")
                continue
        return None

    def download_from_github(self):
        url1 = f"https://raw.githubusercontent.com/{self.github_repo}/main/{self.github_file_path}"
        url2 = f"https://mirror.ghproxy.com/https://raw.githubusercontent.com/{self.github_repo}/main/{self.github_file_path}"
        for url in [url1, url2]:
            try:
                response = requests.get(url, timeout=15)
                response.raise_for_status()
                self.logger.info(f"从{url}下载成功，大小: {len(response.content)}字节")
                return response.content
            except Exception as e:
                self.logger.error(f"从{url}下载失败: {e}")
                continue
        return None

    def get_content_sha1(self, content):
        sha1_hash = hashlib.sha1()
        sha1_hash.update(content)
        return sha1_hash.hexdigest()

    def _cached_remote_sha1(self):
        if self.app_settings is None:
            return ""
        return str(self.app_settings.settings.get("remote_db_sha1") or "")

    def _save_cached_remote_sha1(self, sha1_value):
        if self.app_settings is not None:
            self.app_settings.settings["remote_db_sha1"] = sha1_value
            self.app_settings.save()

    def _report_status(self, status):
        self.logger.info(f"状态报告: {status}")
        if self.app_settings is not None:
            self.app_settings.set_update_check_status(status)

    def manual_check_for_update(self) -> Dict[str, Any]:
        self._report_status("正在检查更新...")
        self.logger.info("手动检查更新开始")

        remote_sha = self.get_remote_sha_safe()
        if not remote_sha:
            self._report_status("连接失败：无法获取远程版本信息")
            return {"ok": False, "message": "连接失败：无法获取远程版本信息"}

        self._report_status("正在下载云端数据库...")

        content = self.download_from_github()
        if not content:
            self._report_status("下载失败：网络错误")
            return {"ok": False, "message": "下载失败：网络错误，无法获取数据库"}

        local_sha1 = self.get_local_sha1()
        remote_content_sha1 = self.get_content_sha1(content)

        if local_sha1 == remote_content_sha1:
            self._report_status("云端版本未变化，无需下载")
            self._save_cached_remote_sha1(remote_sha)
            return {"ok": True, "message": "已是最新版本", "up_to_date": True}

        self._report_status("正在对比差异...")
        self.logger.info(f"检测到差异: 本地={local_sha1}, 云端={remote_content_sha1}")

        try:
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                tmp.write(content)
                temp_file = tmp.name
        except Exception as e:
            self._report_status("处理失败：无法写入临时文件")
            return {"ok": False, "message": f"处理失败: {e}"}

        dialog_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "db_update_dialog.py")

        try:
            if getattr(sys, 'frozen', False):
                proc = subprocess.run(
                    [sys.executable, '--db-update-dialog', self.local_db_path, temp_file],
                    capture_output=True, text=True, timeout=120,
                )
            else:
                proc = subprocess.run(
                    [sys.executable, dialog_script, self.local_db_path, temp_file],
                    capture_output=True, text=True, timeout=120,
                )
        except subprocess.TimeoutExpired:
            self._report_status("差异对比超时")
            try: os.remove(temp_file)
            except: pass
            return {"ok": False, "message": "差异对比超时"}
        except Exception as e:
            self._report_status(f"差异对比失败: {e}")
            try: os.remove(temp_file)
            except: pass
            return {"ok": False, "message": f"差异对比失败: {e}"}

        try: os.remove(temp_file)
        except: pass

        if "ACCEPTED" in proc.stdout:
            self._report_status("已采纳更新")
            self._save_cached_remote_sha1(remote_sha)
            if self.app_settings is not None:
                self.app_settings.mark_database_updated_by_app()
            return {"ok": True, "message": "已采纳更新", "accepted": True}
        else:
            self._report_status("已放弃更新")
            self._save_cached_remote_sha1(remote_sha)
            return {"ok": True, "message": "已放弃更新", "rejected": True}

    def force_download_and_diff(self) -> Dict[str, Any]:
        self._report_status("正在强制下载云端数据库...")
        self.logger.info("用户触发强制下载")

        content = self.download_from_github()
        if not content:
            self._report_status("强制下载失败：网络错误")
            self.logger.warning("强制下载失败")
            return {"ok": False, "message": "下载失败：网络错误，无法获取数据库"}

        self.logger.info("强制下载完成，启动差异对比...")

        try:
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                tmp.write(content)
                temp_file = tmp.name
        except Exception as e:
            self.logger.error(f"写入临时文件失败: {e}")
            self._report_status("强制下载失败：无法写入临时文件")
            return {"ok": False, "message": f"写入临时文件失败: {e}"}

        dialog_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "db_update_dialog.py")

        try:
            if getattr(sys, 'frozen', False):
                proc = subprocess.run(
                    [sys.executable, '--db-update-dialog', self.local_db_path, temp_file],
                    capture_output=True, text=True, timeout=120,
                )
            else:
                proc = subprocess.run(
                    [sys.executable, dialog_script, self.local_db_path, temp_file],
                    capture_output=True, text=True, timeout=120,
                )
        except subprocess.TimeoutExpired:
            self._report_status("差异对比超时")
            try:
                os.remove(temp_file)
            except Exception:
                pass
            return {"ok": False, "message": "差异对比超时"}
        except Exception as e:
            self._report_status(f"启动差异对比失败: {e}")
            try:
                os.remove(temp_file)
            except Exception:
                pass
            return {"ok": False, "message": f"启动差异对比失败: {e}"}

        try:
            os.remove(temp_file)
        except Exception:
            pass

        if "ACCEPTED" in proc.stdout:
            updated_sha1 = self.get_local_sha1()
            remote_sha = self.get_remote_sha_safe() or ""
            self._save_cached_remote_sha1(remote_sha)
            if self.app_settings is not None:
                self.app_settings.mark_database_updated_by_app()
            self._report_status("已采纳更新")
            self.logger.info(f"用户采纳强制更新，本地SHA1: {updated_sha1}")
            return {"ok": True, "message": "已采纳更新"}
        else:
            remote_sha = self.get_remote_sha_safe() or ""
            self._save_cached_remote_sha1(remote_sha)
            self._report_status("云端版本未变化，无需下载")
            self.logger.info("用户放弃强制更新")
            return {"ok": True, "message": "已放弃更新"}
