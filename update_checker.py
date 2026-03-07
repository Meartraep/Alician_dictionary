import hashlib
import os
import requests
import tkinter as tk
from tkinter import messagebox
import threading

class UpdateChecker:
    """更新检查器，用于检测和更新translated.db文件"""
    
    def __init__(self, local_db_path):
        self.local_db_path = local_db_path
        self.github_repo = "Meartraep/Alician_dictionary"
        self.github_file_path = "translated.db"
        self.cdn_url = "https://cdn.jsdelivr.net/gh/Meartraep/Alician_dictionary@main/translated.db"
        self.update_needed = False
        self.update_content = None
        self.check_completed = False
        
    def get_local_sha1(self):
        """计算本地文件的SHA1值"""
        if not os.path.exists(self.local_db_path):
            return None
        
        sha1_hash = hashlib.sha1()
        with open(self.local_db_path, "rb") as f:
            # 分块读取文件以处理大文件
            while chunk := f.read(4096):
                sha1_hash.update(chunk)
        return sha1_hash.hexdigest()
    
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
                print(f"从{url}获取SHA值成功")
                return data.get("sha")
            except Exception as e:
                print(f"从{url}获取SHA值失败: {e}")
                continue
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
                print(f"从{url}获取文件内容成功")
                return response.content
            except Exception as e:
                print(f"从{url}获取文件内容失败: {e}")
                continue
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
            return True
        except Exception as e:
            print(f"从GitHub下载失败: {e}")
            return False
    
    def download_from_cdn(self):
        """从CDN下载文件"""
        try:
            response = requests.get(self.cdn_url, timeout=15)
            response.raise_for_status()
            
            # 写入文件
            with open(self.local_db_path, "wb") as f:
                f.write(response.content)
            return True
        except Exception as e:
            print(f"从CDN下载失败: {e}")
            return False
    
    def check_for_update(self):
        """检查是否需要更新（后台执行）"""
        print("开始后台检查更新...")
        
        # 获取本地SHA1
        local_sha1 = self.get_local_sha1()
        
        # 方法1：尝试通过文件内容比较（优先）
        github_content = self.get_github_content()
        if github_content:
            # 计算远程内容的SHA1
            remote_sha1 = self.get_content_sha1(github_content)
            
            # 检查是否需要更新
            if local_sha1 == remote_sha1:
                print(f"数据库文件已是最新版本: SHA1={local_sha1}")
                self.update_needed = False
            else:
                print(f"检测到更新: 本地SHA1={local_sha1}, 远程SHA1={remote_sha1}")
                self.update_needed = True
                self.update_content = github_content
        else:
            print("方法1失败，尝试方法2")
            # 方法2：尝试通过GitHub API获取SHA值比较
            remote_github_sha = self.get_remote_sha_safe()
            if remote_github_sha:
                # 无法直接比较SHA，但网络连接正常，尝试下载
                github_content = self.get_github_content()
                if github_content:
                    remote_sha1 = self.get_content_sha1(github_content)
                    if local_sha1 != remote_sha1:
                        print(f"检测到更新: 本地SHA1={local_sha1}")
                        self.update_needed = True
                        self.update_content = github_content
                    else:
                        print(f"数据库文件已是最新版本: SHA1={local_sha1}")
                        self.update_needed = False
                else:
                    print("无法获取文件内容，跳过更新")
                    self.update_needed = False
            else:
                print("方法2失败，无法检查更新")
                self.update_needed = False
        
        self.check_completed = True
        print(f"后台检查完成，需要更新: {self.update_needed}")
    
    def perform_update(self, parent_window=None):
        """执行更新操作"""
        if not self.update_needed or not self.update_content:
            print("无需更新")
            return True
        
        print("开始执行更新...")
        
        # 直接使用获取到的内容写入文件
        try:
            with open(self.local_db_path, "wb") as f:
                f.write(self.update_content)
            print("从GitHub更新成功")
            return True
        except Exception as e:
            print(f"写入文件失败: {e}")
            
            # 尝试从CDN下载
            print("尝试从CDN下载")
            if self.download_from_cdn():
                print("从CDN更新成功")
                return True
        
        # 所有下载都失败
        print("更新失败")
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