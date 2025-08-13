import sys
import traceback
import subprocess
from reapy import reascript_api as rpp
import reapy
import psutil
import stat
import os
import time
import tkinter as tk
from tkinter import filedialog
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout,
                            QMessageBox, QLabel, QHBoxLayout,QProgressDialog
                            )
from PyQt5.QtGui import QPixmap, QIcon, QPalette, QBrush
from PyQt5.QtCore import Qt,QThread, pyqtSignal, QTimer,QSettings
from waapi import WaapiClient,CannotConnectToWaapiException
import requests

CONFIG_FILE = 'reaperconfig.txt'

APP_VERSION = "1.0.2"  
UPDATE_URL = "https://raw.githubusercontent.com/FreshSoul/Wreaper/main/src/dist/wreaper/wreaper.exe"
VERSION_FILE_URL = "https://raw.githubusercontent.com/FreshSoul/Wreaper/main/version.txt"



def get_remote_version():
    try:
        resp = requests.get(VERSION_FILE_URL, timeout=5)
        if resp.status_code == 200:
            return resp.text.strip()
    except Exception as e:
        print("检查更新失败：", e)
    return None

def is_new_version(local_version, remote_version):
    def parse(v):
        return tuple(int(x) for x in v.split('.'))
    try:
        return parse(remote_version) > parse(local_version)
    except Exception:
        return local_version != remote_version

def download_new_version():  # 保留旧函数（若别处引用），但标记不再直接在 UI 线程使用
    """
    同步下载（已被线程版本替代），保留以兼容；不要在 GUI 线程调用。
    """
    url = UPDATE_URL
    save_path = "wreaper_new.exe"
    try:
        resp = requests.get(url, stream=True)
        with open(save_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print("下载新版本失败：", e)
        return False

def replace_and_restart():
    bat_content = (
        "@echo off\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        "taskkill /f /im wreaper.exe >nul 2>&1\r\n"
        "if exist wreaper_new.exe (\r\n"
        "  del /f /q wreaper.exe >nul 2>&1\r\n"
        "  ren wreaper_new.exe wreaper.exe\r\n"
        "  start \"\" wreaper.exe\r\n"
        ") else (\r\n"
        "  echo 未找到新文件\r\n"
        "  pause\r\n"
        ")\r\n"
    )
    with open("update.bat", "w", encoding="utf-8") as f:
        f.write(bat_content)
    os.startfile("update.bat")
    sys.exit()

class DownloadThread(QThread):
    progress = pyqtSignal(int)              # 百分比
    finished = pyqtSignal(bool, str)        # (成功?, 错误信息)

    def __init__(self, url, save_path, parent=None):
        super().__init__(parent)
        self.url = url
        self.save_path = save_path
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            resp = requests.get(self.url, stream=True, timeout=15)
            resp.raise_for_status()
            total = int(resp.headers.get('content-length', 0))
            downloaded = 0
            with open(self.save_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if self._cancel:
                        self.finished.emit(False, "用户取消")
                        return
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = int(downloaded * 100 / total)
                        self.progress.emit(pct)
            self.progress.emit(100)
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))






class Wreaper(QWidget):

#前端
    def __init__(self):
        super().__init__()
        self.settings = QSettings("Wreaper", "WreaperApp")
        self.wwise_client = None
        self.download_thread = None
        self.progress_dialog = None
        self.initUI()
        QTimer.singleShot(300, self.check_update_and_prompt_async)

    def initUI(self):
        # 优先加载用户自定义背景
        bg_path = self.settings.value("bg_image_path", "test.jpg")
        if not os.path.exists(bg_path):
            bg_path = "test.jpg"
        self.set_background_image(bg_path)
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 顶部标题区域
        title_layout = QHBoxLayout()

        # 图标
        self.logo_label = QLabel()

        self.logo_label.setPixmap(QPixmap("WwiseLogo.png").scaled(80, 80, Qt.KeepAspectRatio))
        title_layout.addWidget(self.logo_label)

        # 标题文本
        # title_text = QLabel("Wreaper")
        # title_font = QFont()
        # title_font.setFamily("Arial Rounded MT Bold")
        # title_font.setPointSize(50)
        # title_font.setBold(True)
        # title_text.setFont(title_font)
        # title_text.setStyleSheet("color: #000000;")
        # title_layout.addWidget(title_text)

        # 添加弹性空间使标题居中
        title_layout.addStretch()
        main_layout.addLayout(title_layout)

        separator = QLabel()
        separator.setStyleSheet("background-color: #000000; height: 2px;")
        separator.setFixedHeight(2)
        main_layout.addWidget(separator)

        button_layout = QVBoxLayout()
        button_layout.setSpacing(15)

        # 按钮1 - 配置Reaper启动路径
        self.button1 = self.create_anime_button("配置Reaper启动路径", "#000000", "#5E9DD1")
        self.button1.clicked.connect(self.Select_reaperconfig)
        button_layout.addWidget(self.button1)
        # 按钮2 - 启动Reaper
        self.button2 = self.create_anime_button("启动Reaper", "#000000", "#5E9DD1")
        self.button2.clicked.connect(self.StartReaper)
        button_layout.addWidget(self.button2)
        # 按钮2 - 导入Reaper
        self.button3 = self.create_anime_button("导入Reaper", "#000000", "#5E9DD1")
        self.button3.clicked.connect(self.start_reaper_and_open_audio)
        button_layout.addWidget(self.button3)

        # 按钮3 - 渲染回Wwise
        self.button4 = self.create_anime_button("渲染回Wwise", "#000000", "#5E9DD1")
        self.button4.clicked.connect(self.execute_rendering)
        button_layout.addWidget(self.button4)
        main_layout.addLayout(button_layout)

        self.button_update = self.create_anime_button("检查更新", "#000000", "#5E9DD1")
        self.button_update.clicked.connect(self.check_update_and_prompt_async)
        button_layout.addWidget(self.button_update)
        
        # 按钮5 - 更换背景图
        self.button_bg = self.create_anime_button("更换背景图", "#000000", "#5E9DD1")
        self.button_bg.clicked.connect(self.change_background_image)
        button_layout.addWidget(self.button_bg)
        # 底部状态区域
        status_layout = QHBoxLayout()
        self.status_label = QLabel("蓝莓派出品")
        self.status_label.setStyleSheet("color: #000000; font-style: italic;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        # 小图标
        anime_icon = QLabel()
        anime_icon.setPixmap(QPixmap("reaperLogo.jpg").scaled(30, 30, Qt.KeepAspectRatio))
        status_layout.addWidget(anime_icon)

        main_layout.addLayout(status_layout)

        self.setLayout(main_layout)
        self.setWindowTitle('Wreaper')
        self.setWindowIcon(QIcon("test.jpg"))
        self.setGeometry(200, 200, 385, 450)

        # 设置窗口背景
        self.setStyleSheet("""
               QWidget {
                  
                   color: #333333;
                   font-size: 14px;
                   font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
               }
               QPushButton {
                   border: 2px solid #FFFFFF;
                   border-radius: 15px;
                   padding: 15px;
                   font-weight: bold;
                   font-size: 16px;
                   color: white;
                   text-align: center;
                   min-width: 200px;
               }
               QPushButton:hover {
                   border: 2px solid #FFFFFF;
                   opacity: 0.9;
               }
               QPushButton:pressed {
                   position: relative;
                   top: 1px;
                   left: 1px;
               }
           """)

    def create_anime_button(self, text, color1, color2):
        button = QPushButton(text)
        button.setStyleSheet(f"""
            QPushButton {{
                background: rgba({self.hex_to_rgb(color1)}, 0.1);
                border: 2px solid {color1};
                border-radius: 15px;
                padding: 15px;
                font-weight: bold;
                font-size: 16px;
                color: {color1};
                text-align: center;
                min-width: 200px;
            }}
            QPushButton:hover {{
                background: rgba({self.hex_to_rgb(color1)}, 0.2);
                border: 2px solid {color1};
                color: {color2};
            }}
            QPushButton:pressed {{
                background: rgba({self.hex_to_rgb(color2)}, 0.3);
                color: white;
                position: relative;
                top: 1px;
                left: 1px;
            }}
        """)
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedHeight(60)
        return button

    # 新增的辅助方法，用于将十六进制颜色转换为RGB格式
    def hex_to_rgb(self, hex_color):
        """将#RRGGBB格式转换为r, g, b格式"""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f"{r}, {g}, {b}"


    def change_background_image(self):
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(
            title="选择背景图片",
            filetypes=[("图片文件", "*.jpg *.png *.jpeg *.bmp *.gif")]
        )
        if file_path:
            self.set_background_image(file_path)
            # 用 QSettings 保存
            self.settings.setValue("bg_image_path", file_path)

    def check_update_and_prompt_async(self):
            remote_version = get_remote_version()
            if remote_version and is_new_version(APP_VERSION, remote_version):
                reply = QMessageBox.question(self, "发现新版本",
                                            f"检测到新版本 {remote_version}，是否下载并更新？",
                                            QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.start_download_update()
            elif remote_version :
                QMessageBox.information(self, "已是最新版本", f"当前已是最新版本 {APP_VERSION}")
            else:
                QMessageBox.warning(self, "检查失败", "无法获取远程版本信息，请检查网络连接。")
       

    def start_download_update(self):
        if self.download_thread and self.download_thread.isRunning():
            return
        self.progress_dialog = QProgressDialog("下载更新中...", "取消", 0, 100, self)
        self.progress_dialog.setWindowTitle("更新")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.canceled.connect(self.cancel_download_update)
        self.progress_dialog.show()

        self.download_thread = DownloadThread(UPDATE_URL, "wreaper_new.exe", self)
        self.download_thread.progress.connect(self.progress_dialog.setValue)
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.start()

    def cancel_download_update(self):
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.cancel()

    def on_download_finished(self, success, error_msg):
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
        if success:
            QMessageBox.information(self, "下载完成", "新版本已下载，程序将自动重启完成更新。")
            replace_and_restart()
        else:
            if error_msg == "用户取消":
                QMessageBox.information(self, "已取消", "已取消更新。")
            else:
                QMessageBox.warning(self, "下载失败", f"下载失败：{error_msg}")

    def set_background_image(self, image_path):
        """设置窗口背景图片"""
        palette = QPalette()
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            # 使用 Window 而非已弃用的 Background
            palette.setBrush(QPalette.Window, QBrush(pixmap.scaled(
                self.size(),
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation
            )))
            self.setPalette(palette)
            self.setAutoFillBackground(True)

    def resizeEvent(self, event):
        self.set_background_image("test.jpg")
        super().resizeEvent(event)

    def safe_wwis_operation(self, func, *args, **kwargs):
        try:
            if not self.wwise_client or not self.wwise_client.is_connected():
                self.wwise_client = WaapiClient()
            return func(*args, **kwargs)
        except CannotConnectToWaapiException:
            self.show_error_message("无法连接到Wwise", "请确保Wwise正在运行")
            return None
        except Exception as e:
            self.show_error_message("Wwise操作错误", str(e))
            print(f"Wwise错误详情: {traceback.format_exc()}")
            return None




#后端逻辑



    def get_selected_audio_files(self):
        try:
            with WaapiClient() as client:
                result = client.call("ak.wwise.ui.getSelectedObjects", options={'return': ['originalFilePath', 'music:playlistRoot']})
                return [obj.get("originalFilePath") for obj in result.get("objects", []) if obj.get("originalFilePath")]
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法连接到Wwise: {str(e)}")
            return []

    def get_default_reaper_path(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as file:
                path = file.read().strip()
                if os.path.exists(path):
                    return path
        return None

    def remove_readonly_attribute(self,file_path):
        if os.path.exists(file_path):
            os.chmod(file_path, stat.S_IWRITE)

    def save_reaper_path(self, path):
        with open(CONFIG_FILE, 'w') as file:
            file.write(path)

    def select_new_reaper_project(self):
        root = tk.Tk()
        root.withdraw()
        return filedialog.askopenfilename(title="选择 REAPER 启动文件", filetypes=[("Executable files", "*.exe")])

    def start_reaper(self, reaper_path):
        if os.path.exists(reaper_path):
            subprocess.Popen([reaper_path])
            print(f"Reaper 已启动: {reaper_path}")



    def is_reaper_running(self):
        try:
            for p in psutil.process_iter(['name']):
                if p.info['name'] and p.info['name'].lower() == 'reaper.exe':
                    return True
        except Exception as e:
            self.show_error_message("检测进程失败", str(e))
        return False

    def open_audio_in_reaper(self, audio_paths):
        for audio_path in audio_paths:
            try:
                rpp.InsertMedia(audio_path, 1)
                print(f"已在 Reaper 中打开音频文件: {audio_path}")
            except Exception as e:
                self.show_error_message("导入音频到Reaper时出错", f"{audio_path}\n{str(e)}")
                print(f"导入音频到Reaper时出错: {audio_path}\n{traceback.format_exc()}")

    def show_error_message(self, title, message):
        QMessageBox.critical(self, title, message)

#配置Reaper的启动路径
    def Select_reaperconfig(self):
        reaper_path = self.get_default_reaper_path()
        if reaper_path is None:
            reaper_path = self.select_new_reaper_project()
            if reaper_path:
                self.save_reaper_path(reaper_path)
                QMessageBox.information(self, "路径已保存", f"新路径已保存: {reaper_path}")
        else:
            QMessageBox.information(self,"文件路径已配置",f"Reaper 文件路径已配置{reaper_path}")
#启动Reaper
    def StartReaper(self):
        try:
            reaper_path = self.get_default_reaper_path()
            if reaper_path is None:
                QMessageBox.information(self, "提示", "未找到默认路径，您需要手动选择 Reaper 启动文件。")
                reaper_path = self.select_new_reaper_project()
                if reaper_path:
                    self.save_reaper_path(reaper_path)
            if self.is_reaper_running():
                QMessageBox.information(self, "提示", "Reaper 已经在运行.")
            else:
                print("Reaper 没有启动，正在启动 Reaper...")
                self.start_reaper(reaper_path)
                time.sleep(1)
                # QProcess.startDetached(sys.executable, sys.argv)
                # QApplication.quit()
        except Exception as e:

            print(f"错误详情: {traceback.format_exc()}")



#Wwise To Reaper
    def start_reaper_and_open_audio(self):
        try:
            reaper_path = self.get_default_reaper_path()
            if reaper_path is None:
                print("未找到默认路径，您需要手动选择 Reaper 启动文件.")
                reaper_path = self.select_new_reaper_project()
                if reaper_path:
                    self.save_reaper_path(reaper_path)
            if self.is_reaper_running():
                print("Reaper 已经在运行.")
            else:
                print("Reaper 没有启动，正在启动 Reaper...")
                self.start_reaper(reaper_path)
                time.sleep(1)
            selected_audio_files = self.get_selected_audio_files()
            if selected_audio_files:
                for file_path in selected_audio_files:
                    self.remove_readonly_attribute(file_path)
                self.open_audio_in_reaper(selected_audio_files)
            else:
                print("没有选中的音频文件.")
        except Exception as e:
            self.show_error_message("启动Reaper时出错", str(e))
            print(f"错误详情: {traceback.format_exc()}")

# Reaper To Wwise
    def execute_rendering(self):
        selected_audio_files = self.get_selected_audio_files()
        num_items = rpp.CountSelectedMediaItems(0)
        if num_items == 0:
            rpp.ShowConsoleMsg("没有选中任何音频！\n")
            return

        wwise_map = {os.path.basename(p): p for p in selected_audio_files}
        unmatched = []
        should_render = False

        for i in range(num_items):
            item = rpp.GetSelectedMediaItem(0, i)
            take = rpp.GetActiveTake(item)
            if not take:
                continue
            take_name = rpp.GetTakeName(take)
            if take_name in wwise_map:
                source_path = wwise_map[take_name]
                parent_dir = os.path.dirname(source_path)
                if not os.access(parent_dir, os.W_OK):
                    self.show_error_message("目录不可写", parent_dir)
                    return
                rpp.GetSetProjectInfo(0, "RENDER_SETTINGS", 32, True)
                rpp.GetSetProjectInfo_String(0, "RENDER_FILE", parent_dir, True)
                rpp.GetSetProjectInfo_String(0, "RENDER_PATTERN", "$item", True)
                rpp.ShowConsoleMsg(f"已覆盖渲染: {source_path}\n")
                should_render = True
            else:
                unmatched.append(take_name)

        if unmatched:
            self.show_error_message("文件名不匹配",
                                    "以下Reaper选中项未在Wwise中选中：\n" + "\n".join(unmatched))

        if should_render:
            rpp.Main_OnCommand(41824, 0)



if __name__ == '__main__':
    app = QApplication(sys.argv)
    try:
        window = Wreaper()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"应用程序崩溃: {traceback.format_exc()}")
        QMessageBox.critical(None, "应用程序错误",
                             f"程序发生严重错误:\n{str(e)}\n\n详细信息请查看日志")
