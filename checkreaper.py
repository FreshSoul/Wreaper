import sys
import traceback
import subprocess
import reapy
import psutil
import stat
import os
import time
import tkinter as tk
from tkinter import filedialog
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout,
                             QMessageBox, QLabel, QHBoxLayout)
from PyQt5.QtGui import QPixmap, QFont, QIcon, QPalette, QBrush
from PyQt5.QtCore import Qt, QSize
from waapi import WaapiClient, CannotConnectToWaapiException

MAX_RETRY_COUNT = 3
RETRY_DELAY = 2
CONFIG_FILE = 'reaperconfig.txt'


class Wreaper(QWidget):
    def __init__(self):
        super().__init__()
        self.wwise_client = None
        self.initUI()
        self.setup_error_handling()

    def initUI(self):
        """初始化用户界面"""
        self.set_background_image("test.jpg")
        self.setup_main_layout()
        self.setup_title_section()
        self.setup_buttons()
        self.setup_status_bar()
        self.configure_window()

    def setup_error_handling(self):
        """设置全局异常处理"""
        sys.excepthook = self.handle_uncaught_exception

    def handle_uncaught_exception(self, exc_type, exc_value, exc_traceback):
        """处理未捕获的异常"""
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        self.show_error("未处理的异常", f"发生未处理的错误:\n{error_msg}")
        print(f"未处理异常: {error_msg}")

    def setup_main_layout(self):
        """设置主布局"""
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)
        self.setLayout(self.main_layout)

    def setup_title_section(self):
        """设置标题区域"""
        title_layout = QHBoxLayout()

        # 图标
        self.logo_label = QLabel()
        self.logo_label.setPixmap(QPixmap("WwiseLogo.png").scaled(80, 80, Qt.KeepAspectRatio))
        title_layout.addWidget(self.logo_label)

        # 添加弹性空间使标题居中
        title_layout.addStretch()
        self.main_layout.addLayout(title_layout)

        # 分隔线
        separator = QLabel()
        separator.setStyleSheet("background-color: #000000; height: 2px;")
        separator.setFixedHeight(2)
        self.main_layout.addWidget(separator)

    def setup_buttons(self):
        """设置按钮区域"""
        button_layout = QVBoxLayout()
        button_layout.setSpacing(15)

        # 按钮1 - 配置Reaper启动路径
        self.button1 = self.create_anime_button("配置Reaper启动路径", "#000000", "#5E9DD1")
        self.button1.clicked.connect(self.Select_reaperconfig)
        button_layout.addWidget(self.button1)

        # 按钮2 - 导入Reaper
        self.button2 = self.create_anime_button("导入Reaper", "#000000", "#5E9DD1")
        self.button2.clicked.connect(self.safe_start_reaper_and_open_audio)
        button_layout.addWidget(self.button2)

        # 按钮3 - 渲染回Wwise
        self.button3 = self.create_anime_button("渲染回Wwise", "#000000", "#5E9DD1")
        self.button3.clicked.connect(self.safe_execute_rendering)
        button_layout.addWidget(self.button3)

        self.main_layout.addLayout(button_layout)

    def setup_status_bar(self):
        """设置状态栏"""
        status_layout = QHBoxLayout()
        self.status_label = QLabel("蓝莓派出品")
        self.status_label.setStyleSheet("color: #000000; font-style: italic;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        # 小图标
        anime_icon = QLabel()
        anime_icon.setPixmap(QPixmap("reaperLogo.jpg").scaled(30, 30, Qt.KeepAspectRatio))
        status_layout.addWidget(anime_icon)

        self.main_layout.addLayout(status_layout)

    def configure_window(self):
        """配置窗口属性"""
        self.setWindowTitle('Wreaper')
        self.setWindowIcon(QIcon("test.jpg"))
        self.setGeometry(200, 200, 385, 450)
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
        """创建动漫风格按钮"""
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

    def hex_to_rgb(self, hex_color):
        """将十六进制颜色转换为RGB格式"""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f"{r}, {g}, {b}"

    def set_background_image(self, image_path):
        """设置窗口背景图片"""
        if os.path.exists(image_path):
            palette = QPalette()
            pixmap = QPixmap(image_path)
            palette.setBrush(QPalette.Background, QBrush(pixmap.scaled(
                self.size(),
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation
            )))
            self.setPalette(palette)
            self.setAutoFillBackground(True)
        else:
            print(f"背景图片不存在: {image_path}")

    def resizeEvent(self, event):
        """窗口大小改变时重设背景图片"""
        self.set_background_image("test.jpg")
        super().resizeEvent(event)

    def safe_wwis_operation(self, func, *args, **kwargs):
        """安全执行Wwise操作"""
        try:
            if not self.wwise_client or not self.wwise_client.is_connected():
                self.wwise_client = WaapiClient()
            return func(*args, **kwargs)
        except CannotConnectToWaapiException as e:
            self.show_error("无法连接到Wwise", "请确保Wwise正在运行")
            return None
        except Exception as e:
            self.show_error("Wwise操作错误", str(e))
            print(f"Wwise错误详情: {traceback.format_exc()}")
            return None

    def get_selected_audio_files(self):
        """获取选中的音频文件"""

        def _get_files():
            result = self.wwise_client.call(
                "ak.wwise.ui.getSelectedObjects",
                options={'return': ['originalFilePath', 'music:playlistRoot']}
            )
            return [obj.get("originalFilePath") for obj in result.get("objects", [])
                    if obj.get("originalFilePath")]

        return self.safe_wwis_operation(_get_files) or []

    def get_default_reaper_path(self):
        """获取默认的Reaper路径"""
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as file:
                path = file.read().strip()
                if os.path.exists(path):
                    return path
        return None

    def remove_readonly_attribute(self, file_path):
        """移除文件的只读属性"""
        if os.path.exists(file_path):
            try:
                os.chmod(file_path, stat.S_IWRITE)
            except Exception as e:
                print(f"无法移除只读属性: {file_path}, 错误: {str(e)}")

    def save_reaper_path(self, path):
        """保存Reaper路径"""
        try:
            with open(CONFIG_FILE, 'w') as file:
                file.write(path)
        except Exception as e:
            self.show_error("保存失败", f"无法保存路径: {str(e)}")

    def select_new_reaper_project(self):
        """选择新的Reaper项目"""
        root = tk.Tk()
        root.withdraw()
        try:
            return filedialog.askopenfilename(
                title="选择 REAPER 启动文件",
                filetypes=[("Executable files", "*.exe")]
            )
        except Exception as e:
            self.show_error("选择文件失败", str(e))
            return None

    def start_reaper(self, reaper_path):
        """启动Reaper"""
        if os.path.exists(reaper_path):
            try:
                subprocess.Popen([reaper_path])
                print(f"Reaper 已启动: {reaper_path}")
                return True
            except Exception as e:
                self.show_error("启动失败", f"无法启动Reaper: {str(e)}")
                return False
        else:
            self.show_error("路径无效", "指定的Reaper路径不存在")
            return False

    def is_reaper_running(self):
        """检查Reaper是否正在运行"""
        try:
            return any('reaper.exe' in proc.info['name'].lower()
                       for proc in psutil.process_iter(attrs=['name']))
        except Exception as e:
            print(f"检查Reaper运行状态失败: {str(e)}")
            return False

    def safe_reaper_operation(self, func, *args, **kwargs):
        """
        安全执行Reaper操作，如果连接失败会自动启动Reaper并重试
        """
        retry_count = 0
        last_error = None

        while retry_count < MAX_RETRY_COUNT:
            try:
                # 检查并启用API连接
                if not reapy.is_inside_reaper():
                    reapy.config.enable_dist_api()

                # 尝试执行操作
                return func(*args, **kwargs)

            except Exception as e:
                last_error = e
                retry_count += 1
                print(f"Reaper操作失败，尝试 {retry_count}/{MAX_RETRY_COUNT}: {str(e)}")

                # 如果Reaper未运行，尝试启动
                if not self.is_reaper_running():
                    if self.reaper_path and os.path.exists(self.reaper_path):
                        print("尝试启动Reaper...")
                        subprocess.Popen([self.reaper_path])
                        time.sleep(RETRY_DELAY)  # 等待Reaper启动
                    else:
                        self.show_warning("Reaper未运行", "请先配置并启动Reaper")
                        break
                else:
                    time.sleep(RETRY_DELAY)  # 已运行但连接失败，稍等再试

        # 所有重试都失败
        raise Exception(f"操作失败，重试{MAX_RETRY_COUNT}次后仍无法连接Reaper: {str(last_error)}")

    def open_audio_in_reaper(self, audio_paths):
        """在Reaper中打开音频文件"""
        if not reapy.is_inside_reaper():
            try:
                reapy.config.enable_dist_api()
            except Exception as e:
                self.show_error("连接失败", "无法连接到Reaper API")
                return

        for audio_path in audio_paths:
            try:
                self.remove_readonly_attribute(audio_path)
                reapy.reascript_api.InsertMedia(audio_path, 1)
                print(f"已在 Reaper 中打开音频文件: {audio_path}")
            except Exception as e:
                self.show_error("导入失败", f"无法导入文件 {audio_path}: {str(e)}")

    def Select_reaperconfig(self):
        """配置Reaper的启动路径"""
        reaper_path = self.get_default_reaper_path()
        if reaper_path is None:
            reaper_path = self.select_new_reaper_project()
            if reaper_path:
                self.save_reaper_path(reaper_path)
                self.show_info("路径已保存", f"新路径已保存: {reaper_path}")
        else:
            self.show_info("文件路径已配置", f"Reaper 文件路径已配置: {reaper_path}")

    def safe_start_reaper_and_open_audio(self):
        """安全地启动Reaper并打开音频"""
        try:
            self.start_reaper_and_open_audio()
        except Exception as e:
            self.show_error("操作失败", f"发生错误: {str(e)}")
            print(f"错误详情: {traceback.format_exc()}")

    def start_reaper_and_open_audio(self):
        """启动Reaper并打开音频"""
        reaper_path = self.get_default_reaper_path()
        if reaper_path is None:
            self.show_warning("配置缺失", "请先配置Reaper路径")
            reaper_path = self.select_new_reaper_project()
            if reaper_path:
                self.save_reaper_path(reaper_path)
            else:
                return

        if not self.is_reaper_running():
            print("Reaper 没有启动，正在启动 Reaper...")
            if not self.start_reaper(reaper_path):
                return
            time.sleep(6)  # 等待Reaper完全启动

        selected_audio_files = self.get_selected_audio_files()
        if selected_audio_files:
            self.open_audio_in_reaper(selected_audio_files)
        else:
            self.show_info("无选中文件", "没有选中的音频文件")

    def safe_execute_rendering(self):
        """安全执行渲染操作"""
        try:
            self.execute_rendering()
        except Exception as e:
            self.show_error("渲染失败", f"发生错误: {str(e)}")
            print(f"错误详情: {traceback.format_exc()}")

    def execute_rendering(self):
        """执行渲染回Wwise"""
        selected_audio_files = self.get_selected_audio_files()
        if not selected_audio_files:
            self.show_warning("无选中文件", "没有选中的音频文件")
            return

        try:
            num_items = reapy.reascript_api.CountSelectedMediaItems(0)
            if num_items == 0:
                reapy.reascript_api.ShowConsoleMsg("没有选中任何音频！")
                self.show_warning("无选中项目", "Reaper中没有选中的音频项目")
                return

            Should_render = False

            for i in range(num_items):
                item = reapy.reascript_api.GetSelectedMediaItem(0, i)
                take = reapy.reascript_api.GetActiveTake(item)
                take_name = reapy.reascript_api.GetTakeName(take)
                if take:
                    for file_path in selected_audio_files:
                        if take_name == os.path.basename(file_path):
                            source_path = file_path
                            if source_path:
                                source_path_parent_folder = os.path.dirname(source_path)
                                reapy.reascript_api.GetSetProjectInfo(0, "RENDER_SETTINGS", 32, True)
                                reapy.reascript_api.GetSetProjectInfo_String(0, "RENDER_FILE",
                                                                             source_path_parent_folder, True)
                                reapy.reascript_api.GetSetProjectInfo_String(0, "RENDER_PATTERN", "$item", True)
                                reapy.reascript_api.ShowConsoleMsg(f"已覆盖渲染: {source_path}\n")
                                Should_render = True

            if Should_render:
                reapy.reascript_api.Main_OnCommand(41824, 0)
                self.show_info("渲染完成", "音频已成功渲染回Wwise")
        except Exception as e:
            raise Exception(f"渲染过程中出错: {str(e)}")

    def show_error(self, title, message):
        """显示错误对话框"""
        QMessageBox.critical(self, title, message)

    def show_warning(self, title, message):
        """显示警告对话框"""
        QMessageBox.warning(self, title, message)

    def show_info(self, title, message):
        """显示信息对话框"""
        QMessageBox.information(self, title, message)

    def closeEvent(self, event):
        """关闭时清理资源"""
        if hasattr(self, 'wwise_client') and self.wwise_client and self.wwise_client.is_connected():
            try:
                self.wwise_client.disconnect()
            except:
                pass
        super().closeEvent(event)


if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        window = Wreaper()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        error_msg = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        print(f"应用程序崩溃: {error_msg}")
        QMessageBox.critical(None, "应用程序错误",
                             f"程序发生严重错误:\n{str(e)}\n\n详细信息请查看日志")