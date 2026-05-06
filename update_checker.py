import hashlib
import os
import sys
import requests
from tkinter import messagebox
import threading
import logging

class UpdateChecker:
    """更新检查器，用于检测和更新translated.db文件"""
    
    def __init__(self, local_db_path, app_settings=None):
        self.local_db_path = local_db_path
        self.app_settings = app_settings
        self.github_repo = "Meartraep/Alician_dictionary"
        self.github_file_path = "translated.db"
        self.cdn_url = "https://cdn.jsdelivr.net/gh/Meartraep/Alician_dictionary@main/translated.db"
        self.update_needed = False
        self.update_content = None
        self.check_completed = False
        
        # 配置日志 - 支持打包环境
        if getattr(sys, 'frozen', False):
            # 打包环境 - 使用可执行文件所在目录
            log_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            # 开发环境 - 使用脚本所在目录
            log_dir = os.path.dirname(os.path.abspath(__file__))
        log_file = os.path.join(log_dir, "update_checker.log")
        
        # 配置日志记录器
        self.logger = logging.getLogger("UpdateChecker")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False  # 防止日志重复
        
        # 清空现有处理器
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            handler.close()
        
        try:
            # 创建文件处理器
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            
            # 创建格式化器
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            
            # 添加处理器到记录器
            self.logger.addHandler(file_handler)
            self.logger.info(f"日志文件已配置: {log_file}")
        except Exception as e:
            print(f"配置日志失败: {e}")
        
    def get_local_sha1(self):
        """计算本地文件的SHA1值"""
        if not os.path.exists(self.local_db_path):
            self.logger.info(f"本地数据库文件不存在: {self.local_db_path}")
            return None
        
        sha1_hash = hashlib.sha1()
        with open(self.local_db_path, "rb") as f:
            # 分块读取文件以处理大文件
            while chunk := f.read(4096):
                sha1_hash.update(chunk)
        sha1_value = sha1_hash.hexdigest()
        self.logger.info(f"本地数据库文件SHA1值: {sha1_value}")
        return sha1_value
    
    def get_remote_sha_safe(self):
        """安全获取远程文件的SHA值（多线路支持）"""
        # 线路1：官方
        url1 = f"https://api.github.com/repos/{self.github_repo}/contents/{self.github_file_path}"
        # 线路2：国内加速
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
        self.logger.warning("无法获取远程SHA值")
        return None
    
    def get_github_content(self):
        """从GitHub获取文件内容（多线路支持）"""
        # 线路1：官方
        url1 = f"https://raw.githubusercontent.com/{self.github_repo}/main/{self.github_file_path}"
        # 线路2：国内加速
        url2 = f"https://mirror.ghproxy.com/https://raw.githubusercontent.com/{self.github_repo}/main/{self.github_file_path}"
        
        for url in [url1, url2]:
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                self.logger.info(f"从{url}获取文件内容成功，大小: {len(response.content)}字节")
                return response.content
            except Exception as e:
                self.logger.error(f"从{url}获取文件内容失败: {e}")
                continue
        self.logger.warning("无法获取GitHub文件内容")
        return None
    
    def get_content_sha1(self, content):
        """计算内容的SHA1值"""
        sha1_hash = hashlib.sha1()
        sha1_hash.update(content)
        return sha1_hash.hexdigest()
    
    def download_from_github(self):
        """从GitHub下载文件"""
        try:
            url = f"https://raw.githubusercontent.com/{self.github_repo}/main/{self.github_file_path}"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            # 写入文件
            with open(self.local_db_path, "wb") as f:
                f.write(response.content)
            self.logger.info(f"从GitHub下载成功，文件大小: {len(response.content)}字节")
            return True
        except Exception as e:
            self.logger.error(f"从GitHub下载失败: {e}")
            return False
    
    def download_from_cdn(self):
        """从CDN下载文件"""
        try:
            response = requests.get(self.cdn_url, timeout=15)
            response.raise_for_status()
            
            # 写入文件
            with open(self.local_db_path, "wb") as f:
                f.write(response.content)
            self.logger.info(f"从CDN下载成功，文件大小: {len(response.content)}字节")
            return True
        except Exception as e:
            self.logger.error(f"从CDN下载失败: {e}")
            return False
    
    def check_for_update(self):
        if self.app_settings is not None and not self.app_settings.get_public_settings().get("auto_update", True):
            self.logger.info("自动更新已关闭，跳过后台检查")
            self.check_completed = True
            self.update_needed = False
            return

        """检查是否需要更新（后台执行）"""
        self.logger.info("开始后台检查更新...")
        
        # 获取本地SHA1
        local_sha1 = self.get_local_sha1()
        
        # 方法1：尝试通过文件内容比较（优先）
        github_content = self.get_github_content()
        if github_content:
            # 计算远程内容的SHA1
            remote_sha1 = self.get_content_sha1(github_content)
            
            # 检查是否需要更新
            if local_sha1 == remote_sha1:
                self.logger.info(f"数据库文件已是最新版本: SHA1={local_sha1}")
                self.update_needed = False
            else:
                self.logger.info(f"检测到更新: 本地SHA1={local_sha1}, 远程SHA1={remote_sha1}")
                self.update_needed = True
                self.update_content = github_content
        else:
            self.logger.info("方法1失败，尝试方法2")
            # 方法2：尝试通过GitHub API获取SHA值比较
            remote_github_sha = self.get_remote_sha_safe()
            if remote_github_sha:
                # 无法直接比较SHA，但网络连接正常，尝试下载
                github_content = self.get_github_content()
                if github_content:
                    remote_sha1 = self.get_content_sha1(github_content)
                    if local_sha1 != remote_sha1:
                        self.logger.info(f"检测到更新: 本地SHA1={local_sha1}")
                        self.update_needed = True
                        self.update_content = github_content
                    else:
                        self.logger.info(f"数据库文件已是最新版本: SHA1={local_sha1}")
                        self.update_needed = False
                else:
                    self.logger.warning("无法获取文件内容，跳过更新")
                    self.update_needed = False
            else:
                self.logger.error("方法2失败，无法检查更新")
                self.update_needed = False
        
        self.check_completed = True
        self.logger.info(f"后台检查完成，需要更新: {self.update_needed}")
    
    def perform_update(self, parent_window=None):
        if self.app_settings is not None and not self.app_settings.get_public_settings().get("auto_update", True):
            self.logger.info("自动更新已关闭，跳过写入")
            return True

        if self.app_settings is not None and self.app_settings.detect_local_db_change():
            self.logger.info("检测到本地数据库已更改，跳过自动更新写入")
            return True

        """执行更新操作"""
        if not self.update_needed or not self.update_content:
            self.logger.info("无需更新")
            return True
        
        self.logger.info("开始执行更新...")
        
        # 直接使用获取到的内容写入文件
        try:
            with open(self.local_db_path, "wb") as f:
                f.write(self.update_content)
            # 计算更新后的SHA1值
            updated_sha1 = self.get_local_sha1()
            if self.app_settings is not None:
                self.app_settings.mark_database_updated_by_app()
            self.logger.info(f"从GitHub更新成功，更新后SHA1值: {updated_sha1}")
            return True
        except Exception as e:
            self.logger.error(f"写入文件失败: {e}")
            
            # 尝试从CDN下载
            self.logger.info("尝试从CDN下载")
            if self.download_from_cdn():
                # 计算更新后的SHA1值
                updated_sha1 = self.get_local_sha1()
                if self.app_settings is not None:
                    self.app_settings.mark_database_updated_by_app()
                self.logger.info(f"从CDN更新成功，更新后SHA1值: {updated_sha1}")
                return True
        
        # 所有下载都失败
        self.logger.error("更新失败")
        if parent_window:
            messagebox.showwarning(
                "更新失败",
                f"无法更新数据库文件。\n\n项目GitHub地址: https://github.com/{self.github_repo}\n\n程序将继续使用本地版本运行。"
            )
        return True  # 即使更新失败也继续运行主程序
    
    def start_background_check(self):
        """启动后台检查线程"""
        check_thread = threading.Thread(target=self.check_for_update)
        check_thread.daemon = True
        check_thread.start()
        return check_thread
