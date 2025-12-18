import sys
import traceback
from reapy import reascript_api as rpp
import stat
import os
import time
import asyncio

from matplotlib import rcParams
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QGridLayout,QMessageBox, QLabel,
    QHBoxLayout, QProgressDialog, QSizePolicy, QMenuBar, QFileDialog,QDialog, QTextEdit,QInputDialog
)
from PyQt5.QtGui import QPixmap, QIcon, QPalette, QBrush, QFont
from PyQt5.QtCore import Qt, QTimer, QSettings, QThread, pyqtSignal
from utils.config import (
    APP_VERSION, CONFIG_FILE, VERSION_FILE_URL,
    GITHUB_OWNER, GITHUB_REPO, RELEASE_ASSET_EXE, TAG_PREFIX
)
from backend.wwise_service import WwiseService
from backend.reaper_service import ReaperService
from backend.updater import Updater
from utils.download_thread import DownloadThread
from utils.resources import resource_path
from utils.update_runner import replace_and_restart
from AudioAnalyse import AudioAnalyse as audio_analysis
from AudioAnalyse.AudioAnalysisThread import AudioAnalysisThread
from AudioAnalyse import AnalyseLUFS_Game_Wwise as lufs_game_wwise
from AudioAnalyse.AudioAnalysisThread import AudioAnalysisThread, LufsAnalysisThread
from ForWwise.LoudnessReport import show_loudness_report

rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体
rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

class GetAudioSourcesThread(QThread):
    finished_ok = pyqtSignal(list)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int)
    status = pyqtSignal(str)

    def run(self):
        try:
            # 关键：为当前线程创建事件循环
            try:
                asyncio.set_event_loop(asyncio.new_event_loop())
            except Exception:
                pass
            from AudioAnalyse import AnalyseLUFS_Game_Wwise as lufs_game_wwise
            audio_files = lufs_game_wwise.get_audio_sources(
                progress_callback=self.progress.emit,
                status_callback=self.status.emit
            )
            if not audio_files:
                self.failed.emit("未找到音频源文件。")
            else:
                self.finished_ok.emit(audio_files)
        except Exception as e:
            self.failed.emit(str(e))





class GetSelectedFilesThread(QThread):
    finished_ok = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service

    def run(self):
        try:
            files = self.service.get_selected_audio_files()
            self.finished_ok.emit(files or [])
        except Exception as e:
            self.failed.emit(str(e))

class Wreaper(QWidget):
    # 前端（UI）
    def __init__(self):
        super().__init__()
        self.settings = QSettings("Wreaper", "WreaperApp")
        # 后端服务实例
        self.wwise_service = WwiseService()
        self.reaper_service = ReaperService()
        self.updater = Updater(VERSION_FILE_URL, "")

        # 下载相关
        self.download_thread = None
        self.progress_dialog = None

        # 音频分析相关
        self.analysis_thread = None
        self.analysis_progress_dialog = None
        
        
        self.initUI()
        # 启动后延时自动检查（不弹“已是最新版本”）
        QTimer.singleShot(300, self.check_update_and_prompt_async)

    def initUI(self):
        # 优先加载用户自定义背景
        bg_path = self.settings.value("bg_image_path", "")
        if not bg_path or not os.path.exists(bg_path):
            bg_path = resource_path("test.jpg")
        self.set_background_image(bg_path)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 菜单栏（放在页边框上）
        menubar = QMenuBar(self)
        menu = menubar.addMenu("功能")
        act_config = menu.addAction("配置Reaper启动路径")
        act_bg = menu.addAction("更换背景图")
        act_checkupdate = menu.addAction("检查更新")

        menu_audio = menubar.addMenu("音频分析")
        act_audio_centroid = menu_audio.addAction("音频频谱质心分析")
        act_audio_3d = menu_audio.addAction("音频3D频谱分析")
        act_audio_2d = menu_audio.addAction("音频2D频谱分析")
        act_audio_lufs = menu_audio.addAction("响度数据（Wwise项目）")
        act_loudness_report = menu_audio.addAction("响度报告")
        
        # QAction.triggered 会传 bool(checked)，用 lambda 吞掉并传手动标记
        act_config.triggered.connect(lambda checked=False: self.Select_reaperconfig())
        act_bg.triggered.connect(lambda checked=False: self.change_background_image())
        act_checkupdate.triggered.connect(lambda checked=False: self.check_update_and_prompt_async(manual=True))
        act_audio_centroid.triggered.connect(lambda checked=False: self.audio_analysis_centroid())
        act_audio_3d.triggered.connect(lambda checked=False: self.audio_analysis_3d())
        act_audio_2d.triggered.connect(lambda checked=False: self.audio_analysis_2d())
        act_audio_lufs.triggered.connect(lambda checked=False: self._analyse_audio_files_game_wwise())
        act_loudness_report.triggered.connect(lambda checked=False: self.open_loudness_report())

        main_layout.setMenuBar(menubar)

        # 顶部标题/Logo区域
        title_layout = QHBoxLayout()
        self.logo_label = QLabel()
        self.load_logo()
        title = QLabel()
        f = QFont()
        f.setPointSize(20)
        f.setBold(True)
        title.setFont(f)
        title.setStyleSheet("color:#000000;")
        title_layout.addWidget(self.logo_label)
        title_layout.addSpacing(10)
        title_layout.addWidget(title)
        title_layout.addStretch()
        main_layout.addLayout(title_layout)

        # 分隔线
        separator = QLabel()
        separator.setStyleSheet("background-color: #000000; height: 2px;")
        separator.setFixedHeight(2)
        main_layout.addWidget(separator)

        # 中部按钮区
        button_layout = QGridLayout()
        button_layout.setSpacing(12)

        self.button2 = self.create_anime_button("启动Reaper", "#000000", "#5E9DD1")
        self.button2.clicked.connect(self.StartReaper)
        button_layout.addWidget(self.button2, 0, 0, 1, 2)  # 第一行，跨两列居中

        self.button3 = self.create_anime_button("导入Reaper", "#000000", "#5E9DD1")
        self.button3.clicked.connect(self.start_reaper_and_open_audio)
        button_layout.addWidget(self.button3, 1, 0)  # 第二行左

        self.button4 = self.create_anime_button("所选Item渲染回Wwise", "#000000", "#5E9DD1")
        self.button4.clicked.connect(self.execute_rendering)
        button_layout.addWidget(self.button4, 2, 0)  # 第二行右

        self.button5 = self.create_anime_button("区间导入Reaper", "#000000", "#FF3848")
        self.button5.clicked.connect(self.import_wwise_files_and_create_regions)
        button_layout.addWidget(self.button5, 1, 1)  # 第三行左

        self.button6 = self.create_anime_button("区间渲染回Wwise", "#000000", "#FF3848")
        self.button6.clicked.connect(self.Region_rendering)
        button_layout.addWidget(self.button6, 2, 1)  # 第三行右

        main_layout.addLayout(button_layout)

        # 底部状态区域
        status_layout = QHBoxLayout()
        self.status_label = QLabel("ALL FOR AUDIO")
        self.status_label.setStyleSheet("color: #000000; font-style: italic;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        self.version_label = QLabel(f"v{APP_VERSION}")
        self.version_label.setStyleSheet("color: #000000; font-style: italic;")
        status_layout.addWidget(self.version_label)
        anime_icon = QLabel()
        anime_icon_pix = QPixmap(resource_path("reaperLogo.jpg"))
        if not anime_icon_pix.isNull():
            anime_icon.setPixmap(anime_icon_pix.scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        status_layout.addWidget(anime_icon)
        main_layout.addLayout(status_layout)

        self.setLayout(main_layout)
        self.setWindowTitle('')
        self.setWindowIcon(QIcon(resource_path("test.jpg")))
        self.setGeometry(200, 200, 420, 520)

        # 统一样式
        self.setStyleSheet("""
            QWidget { color: #333333; font-size: 14px; font-family: 'Segoe UI','Microsoft YaHei',sans-serif; }
            QPushButton {
                border: 2px solid #FFFFFF; border-radius: 15px; padding: 15px;
                font-weight: bold; font-size: 16px; color: white; text-align: center; min-width: 200px;
            }
            QPushButton:hover { border: 2px solid #FFFFFF; opacity: 0.9; }
            QPushButton:pressed { position: relative; top: 1px; left: 1px; }
        """)


    def show_long_message(self, title, message):
            dlg = QDialog(self)
            dlg.setWindowTitle(title)
            dlg.setMinimumSize(600, 400)
            layout = QVBoxLayout(dlg)
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setText(message)
            layout.addWidget(text_edit)
            btn_layout = QHBoxLayout()
            btn_ok = QPushButton("确定")
            btn_ok.clicked.connect(dlg.accept)
            btn_layout.addStretch()
            btn_layout.addWidget(btn_ok)
            layout.addLayout(btn_layout)
            dlg.exec_()


    def load_logo(self):
        logo_path = resource_path("WwiseLogo.png")
        pix = QPixmap(logo_path)
        if not pix.isNull():
            self.logo_label.setPixmap(pix.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            print(f"[Logo] 加载失败: {logo_path}")

    def create_anime_button(self, text, color1, color2):
        button = QPushButton(text)
        button.setStyleSheet(f"""
            QPushButton {{
                background: rgba({self.hex_to_rgb(color1)}, 0.10);
                border: 2px solid {color1};
                border-radius: 15px;
                padding: 14px;
                font-weight: bold;
                font-size: 16px;
                color: {color1};
            }}
            QPushButton:hover {{
                background: rgba({self.hex_to_rgb(color1)}, 0.20);
                border: 2px solid {color1};
                color: {color2};
            }}
            QPushButton:pressed {{
                background: rgba({self.hex_to_rgb(color2)}, 0.30);
                color: white;
                position: relative;
                top: 1px;
                left: 1px;
            }}
        """)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        button.setMinimumHeight(60)
        return button

    # 十六进制颜色 -> r,g,b
    def hex_to_rgb(self, hex_color):
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f"{r}, {g}, {b}"

    # 背景图相关
    def set_background_image(self, image_path):
        palette = QPalette()
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            palette.setBrush(
                QPalette.Window,
                QBrush(pixmap.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
            )
            self.setPalette(palette)
            self.setAutoFillBackground(True)

    def resizeEvent(self, event):
        bg_path = self.settings.value("bg_image_path", "")
        if not bg_path or not os.path.exists(bg_path):
            bg_path = resource_path("test.jpg")
        self.set_background_image(bg_path)
        super().resizeEvent(event)

    def change_background_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择背景图片",
            "", # 默认目录
            "图片文件 (*.jpg *.png *.jpeg *.bmp *.gif)"
        )
        if file_path:
            self.set_background_image(file_path)
            self.settings.setValue("bg_image_path", file_path)

    # 更新检查
    def check_update_and_prompt_async(self, manual=False):
        try:
            remote_version = self.updater.get_remote_version()
        except Exception as e:
            if manual:
                QMessageBox.warning(self, "检查失败", f"无法获取远程版本信息：{e}")
            return

        self._remote_version = remote_version  # 记录待下载的远程版本

        if remote_version and self.updater.is_new_version(APP_VERSION, remote_version):
            reply = QMessageBox.question(
                self, "发现新版本",
                f"检测到新版本 {remote_version}，是否下载并更新？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.start_download_update()
        elif remote_version:
            if manual:
                QMessageBox.information(self, "已是最新版本", f"当前已是最新版本（{APP_VERSION}）")

    def start_download_update(self):
        if self.download_thread and self.download_thread.isRunning():
            return
        if getattr(self, "_remote_version", None):
            url = self.updater.build_release_asset_url(
                GITHUB_OWNER, GITHUB_REPO, self._remote_version, RELEASE_ASSET_EXE, TAG_PREFIX
            )
            self.updater.update_url = url
        self.progress_dialog = QProgressDialog("下载更新中...", "取消", 0, 100, self)
        self.progress_dialog.setWindowTitle("更新")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.canceled.connect(self.cancel_download_update)
        self.progress_dialog.show()

        self.download_thread = DownloadThread(self.updater, "Wreaper_new.exe", self)
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
                
##############################################################################################
    # 路径/文件与 Reaper 相关
    def get_default_reaper_path(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as file:
                path = file.read().strip()
                if os.path.exists(path):
                    return path
        return None

    def remove_readonly_attribute(self, file_path):
        if os.path.exists(file_path):
            os.chmod(file_path, stat.S_IWRITE)

    def save_reaper_path(self, path):
        with open(CONFIG_FILE, 'w') as file:
            file.write(path)

    def select_new_reaper_project(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 REAPER 启动文件",
            "", # 默认目录
            "可执行文件 (*.exe)"
        )
        return file_path

    def show_error_message(self, title, message):
        QMessageBox.critical(self, title, message)

    # 菜单行为
    def Select_reaperconfig(self):
        reaper_path = self.get_default_reaper_path()
        if reaper_path is None:
            reaper_path = self.select_new_reaper_project()
            if reaper_path:
                self.save_reaper_path(reaper_path)
                QMessageBox.information(self, "路径已保存", f"新路径已保存: {reaper_path}")
        else:
            QMessageBox.information(self, "文件路径已配置", f"Reaper 文件路径已配置：\n{reaper_path}")

    def StartReaper(self):
        try:
            reaper_path = self.get_default_reaper_path()
            if reaper_path is None:
                QMessageBox.information(self, "提示", "未找到默认路径，您需要手动选择 Reaper 启动文件。")
                reaper_path = self.select_new_reaper_project()
                if reaper_path:
                    self.save_reaper_path(reaper_path)

            if self.reaper_service.is_reaper_running():
                QMessageBox.information(self, "提示", "Reaper 已经在运行。")
            else:
                self.reaper_service.start_reaper(reaper_path)
                time.sleep(1)
        except Exception as e:
            self.show_error_message("启动Reaper时出错", str(e))
            print(f"错误详情: {traceback.format_exc()}")

    # Wwise -> Reaper
    def get_selected_audio_files(self):
        try:
            return self.wwise_service.get_selected_audio_files()
        except Exception as e:
            self.show_error_message("Wwise错误", str(e))
            return []

    def start_reaper_and_open_audio(self):
        try:
            reaper_path = self.get_default_reaper_path()
            if reaper_path is None:
                print("未找到默认路径，您需要手动选择 Reaper 启动文件。")
                reaper_path = self.select_new_reaper_project()
                if reaper_path:
                    self.save_reaper_path(reaper_path)

            if not self.reaper_service.is_reaper_running():
                self.reaper_service.start_reaper(reaper_path)
                time.sleep(1)

            # 子线程获取，避免阻塞
            self.fetch_dialog = QProgressDialog("正在从 Wwise 获取选中对象...", None, 0, 0, self)
            self.fetch_dialog.setWindowTitle("请稍候")
            self.fetch_dialog.setCancelButton(None)
            self.fetch_dialog.setWindowModality(Qt.WindowModal)
            self.fetch_dialog.show()

            self.wwise_thread = GetSelectedFilesThread(self.wwise_service, self)
            self.wwise_thread.finished_ok.connect(self._on_got_wwise_files)
            self.wwise_thread.failed.connect(self._on_wwise_files_failed)
            self.wwise_thread.start()

        except Exception as e:
            self.show_error_message("启动Reaper时出错", str(e))
            print(f"错误详情: {traceback.format_exc()}")

    def _on_got_wwise_files(self, selected_audio_files):
        if getattr(self, "fetch_dialog", None):
            self.fetch_dialog.close()
            self.fetch_dialog = None
        if selected_audio_files:
            for file_path in selected_audio_files:
                self.remove_readonly_attribute(file_path)
            try:
                self.reaper_service.open_audio_in_reaper(selected_audio_files)
            except Exception as e:
                self.show_error_message("导入音频到Reaper时出错", f"{e}\n请尝试重启Wreaper")
        else:
            print("没有选中的音频文件。")

    def _on_wwise_files_failed(self, message):
        if getattr(self, "fetch_dialog", None):
            self.fetch_dialog.close()
            self.fetch_dialog = None
        self.show_error_message("Wwise错误", message)

    # Reaper -> Wwise（覆盖渲染）
    def execute_rendering(self):
        # 检查 Reaper 是否运行
        if not self.reaper_service.is_reaper_running():
            QMessageBox.warning(self, "Reaper未运行", "请先启动 Reaper 再进行渲染操作。")
            return
        
        
        # 采样率选择
        sample_rates = ["32000","44100", "48000", "96000",]
        sr, ok = QInputDialog.getItem(self, "选择采样率", "采样率 (Hz):", sample_rates, 2, False)
        if not ok:
            return

        # 通道数选择
        channels = ["1", "2", "4", "6", "8"]
        ch, ok = QInputDialog.getItem(self, "选择通道数", "通道数:", channels, 0, False)
        if not ok:
            return
    
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
                rpp.GetSetProjectInfo(0, "RENDER_SRATE", int(sr), True)      # 设置采样率
                rpp.GetSetProjectInfo(0, "RENDER_CHANNELS", int(ch), True) 
                should_render = True
            else:
                unmatched.append(take_name)

        if unmatched:
            self.show_error_message("文件名不匹配", "以下Reaper选中项未在Wwise中选中：\n" + "\n".join(unmatched))

        if should_render:
            rpp.Main_OnCommand(41824, 0)

###########################################################################################
    # 区间渲染相关
    #Wwise-->reaper
    def _on_got_wwise_files_Region(self, selected_audio_files):
        if getattr(self, "fetch_dialog", None):
            self.fetch_dialog.close()
            self.fetch_dialog = None
        if selected_audio_files:
            for file_path in selected_audio_files:
                self.remove_readonly_attribute(file_path)
            try:
                self.reaper_service.open_audioRegion_in_reaper(selected_audio_files)
            except Exception as e:
                self.show_error_message("导入音频到Reaper时出错", f"{e}\n请尝试重启Wreaper")
        else:
            print("没有选中的音频文件。")
    
    def import_wwise_files_and_create_regions(self):
        try:
            reaper_path = self.get_default_reaper_path()
            if reaper_path is None:
                print("未找到默认路径，您需要手动选择 Reaper 启动文件。")
                reaper_path = self.select_new_reaper_project()
                if reaper_path:
                    self.save_reaper_path(reaper_path)

            if not self.reaper_service.is_reaper_running():
                self.reaper_service.start_reaper(reaper_path)
                time.sleep(1)

            # 子线程获取，避免阻塞
            self.fetch_dialog = QProgressDialog("正在从 Wwise 获取选中对象...", None, 0, 0, self)
            self.fetch_dialog.setWindowTitle("请稍候")
            self.fetch_dialog.setCancelButton(None)
            self.fetch_dialog.setWindowModality(Qt.WindowModal)
            self.fetch_dialog.show()

            self.wwise_thread = GetSelectedFilesThread(self.wwise_service, self)
            self.wwise_thread.finished_ok.connect(self._on_got_wwise_files_Region)
            self.wwise_thread.failed.connect(self._on_wwise_files_failed)
            self.wwise_thread.start()

        except Exception as e:
            self.show_error_message("启动Reaper时出错", str(e))
            print(f"错误详情: {traceback.format_exc()}")

    #reaper-->Wwise
    def Region_rendering(self):
        if not self.reaper_service.is_reaper_running():
            QMessageBox.warning(self, "Reaper未运行", "请先启动 Reaper 再进行渲染操作。")
            return


        # 采样率选择
        sample_rates = ["32000","44100", "48000", "96000",]
        sr, ok = QInputDialog.getItem(self, "选择采样率", "采样率 (Hz):", sample_rates, 2, False)
        if not ok:
            return

        # 通道数选择
        channels = ["1", "2", "4", "6", "8"]
        ch, ok = QInputDialog.getItem(self, "选择通道数", "通道数:", channels, 0, False)
        if not ok:
            return
        
        
        selected_audio_files = self.get_selected_audio_files()
        wwise_map = {os.path.splitext(os.path.basename(p))[0]: p for p in selected_audio_files}
        unmatched = []
        should_render = False
        num_regions = rpp.CountProjectMarkers(0, 0, 0)
        output_dir = None

        for i in range(num_regions[3]+1):
            fs = rpp.SNM_CreateFastString("")
            rpp.SNM_GetProjectMarkerName(0, i, 1, fs)
            region_name = rpp.SNM_GetFastString(fs)
            if region_name in wwise_map:
                source_path = wwise_map[region_name]
                parent_dir = os.path.dirname(source_path)
                if not os.access(parent_dir, os.W_OK):
                    self.show_error_message("目录不可写", parent_dir)
                    rpp.SNM_DeleteFastString(fs)
                    return
                output_dir = parent_dir 
                should_render = True
            else:
                if region_name:
                    unmatched.append(region_name)
            

        if unmatched:
            self.show_error_message("文件名不匹配", "以下Reaper区间未在Wwise中选中，请全部选中后覆盖渲染：\n" + "\n".join(unmatched))

        if should_render and output_dir:
            
            rpp.GetSetProjectInfo(0, "RENDER_SETTINGS", 0, True)
            rpp.GetSetProjectInfo(0, "RENDER_BOUNDSFLAG", 3, True)
            rpp.GetSetProjectInfo_String(0, "RENDER_FILE", output_dir, True)
            rpp.GetSetProjectInfo_String(0, "RENDER_PATTERN", "$region", True)
            rpp.GetSetProjectInfo(0, "RENDER_SRATE", int(sr), True)      # 设置采样率
            rpp.GetSetProjectInfo(0, "RENDER_CHANNELS", int(ch), True) 
            rpp.Main_OnCommand(41824, 0)




###########################################################################################
    def audio_analysis_2d(self):
        # 选择音频文件夹
        input_dir = audio_analysis.select_directory_2d("请选择包含音频文件的文件夹")
        if not input_dir:
            return

        # 选择输出文件夹
        default_output = os.path.join(input_dir, "频谱图结果")
        output_dir = audio_analysis.select_directory_centroid("请选择输出文件夹", default_output) or default_output

        reply = QMessageBox.question(
            self, "确认",
            f"将从:\n{input_dir}\n生成频谱图到:\n{output_dir}\n\n是否继续?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._start_audio_analysis("2d", input_dir, output_dir)

    def audio_analysis_3d(self):
        input_dir = audio_analysis.select_directory_3d("请选择包含音频文件的文件夹")
        if not input_dir:
            return
        
        default_output_dir = os.path.join(input_dir, "3D频谱图输出")
        output_dir = audio_analysis.select_directory_3d("请选择输出文件夹", default_output_dir) or default_output_dir

        reply = QMessageBox.question(
            self, "确认",
            f"将从:\n{input_dir}\n生成频谱图到:\n{output_dir}\n\n是否继续?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._start_audio_analysis("3d", input_dir, output_dir)
            
    def audio_analysis_centroid(self):

        input_dir = audio_analysis.select_directory_centroid("请选择包含音频文件的文件夹")
        if not input_dir:
            return

        # 选择输出文件夹
        default_output = os.path.join(input_dir, "频谱质心分析结果")
        output_dir = audio_analysis.select_directory_centroid("请选择输出文件夹", default_output) or default_output

        # 使用PyQt5确认对话框（保持与其他功能一致）
        reply = QMessageBox.question(
            self, "确认",
            f"将从:\n{input_dir}\n生成频谱质心分析到:\n{output_dir}\n\n是否继续?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._start_audio_analysis("centroid", input_dir, output_dir)

    def _start_audio_analysis(self, analysis_type, input_dir, output_dir):
        """启动音频分析任务"""
        if self.analysis_thread and self.analysis_thread.isRunning():
            QMessageBox.warning(self, "任务进行中", "已有分析任务正在进行，请等待完成后再试。")
            return

        # 创建进度对话框
        type_names = {"2d": "2D频谱分析", "3d": "3D频谱分析", "centroid": "频谱质心分析"}
        title = type_names.get(analysis_type, "音频分析")
        
        self.analysis_progress_dialog = QProgressDialog(f"正在进行{title}...", "取消", 0, 100, self)
        self.analysis_progress_dialog.setWindowTitle(title)
        self.analysis_progress_dialog.setWindowModality(Qt.WindowModal)
        self.analysis_progress_dialog.setMinimumDuration(0)  # 立即显示
        self.analysis_progress_dialog.canceled.connect(self._cancel_audio_analysis)
        self.analysis_progress_dialog.show()

        # 创建并启动分析线程
        self.analysis_thread = AudioAnalysisThread(analysis_type, input_dir, output_dir, self)
        self.analysis_thread.progress.connect(self.analysis_progress_dialog.setValue)
        self.analysis_thread.status_update.connect(self._update_analysis_status)
        self.analysis_thread.finished_ok.connect(self._on_analysis_finished)
        self.analysis_thread.failed.connect(self._on_analysis_failed)
        self.analysis_thread.start()

    def _update_analysis_status(self, status):
        """更新分析状态文本"""
        if self.analysis_progress_dialog:
            self.analysis_progress_dialog.setLabelText(status)

    def _cancel_audio_analysis(self):
        """取消音频分析"""
        if self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.cancel()

    def _on_analysis_finished(self, result_message):
        """分析完成处理"""
        if self.analysis_progress_dialog:
            self.analysis_progress_dialog.close()
            self.analysis_progress_dialog = None

        QMessageBox.information(self, "处理结果", result_message)
        
        # 打开输出文件夹
        if self.analysis_thread:
            output_dir = self.analysis_thread.output_dir
            if os.name == 'nt':  # Windows
                os.startfile(output_dir)
            elif os.name == 'posix':  # macOS/Linux
                os.system(f'open "{output_dir}"' if sys.platform == 'darwin' else f'xdg-open "{output_dir}"')

    def _on_analysis_failed(self, error_message):
        #分析失败处理
        if self.analysis_progress_dialog:
            self.analysis_progress_dialog.close()
            self.analysis_progress_dialog = None

        if error_message != "用户取消操作":
            QMessageBox.critical(self, "分析失败", error_message)
        else:
            QMessageBox.information(self, "已取消", "音频分析已取消。")

    
    def _analyse_audio_files_game_wwise(self):
    # 先检测 Wwise 端口
        if not self.wwise_service._is_wwise_port_open():
            QMessageBox.warning(self, "Wwise未连接", "无法连接到Wwise，请确保Wwise已启动并启用WAAPI。")
            return

        # 进度对话框
        self.audio_fetch_dialog = QProgressDialog("正在获取Wwise音频对象...", "取消", 0, 100, self)
        self.audio_fetch_dialog.setWindowTitle("获取音频对象")
        self.audio_fetch_dialog.setWindowModality(Qt.WindowModal)
        self.audio_fetch_dialog.setMinimumDuration(0)
        self.audio_fetch_dialog.setValue(0)
        self.audio_fetch_dialog.show()

        # 用线程异步获取音频对象
        self.audio_fetch_thread = GetAudioSourcesThread()
        self.audio_fetch_thread.progress.connect(self.audio_fetch_dialog.setValue)
        self.audio_fetch_thread.status.connect(self.audio_fetch_dialog.setLabelText)
        def on_audio_files_ok(audio_files):
            self.audio_fetch_dialog.close()
            if not audio_files:
                QMessageBox.information(self, "提示", "未找到音频源文件。")
                return

            default_csv = os.path.join(os.getcwd(), "Loudness_Analyse.csv")
            csv_path, _ = QFileDialog.getSaveFileName(
                self,
                "选择分析结果保存位置",
                default_csv,
                "CSV文件 (*.csv)"
            )
            if not csv_path:
                return

            reply = QMessageBox.question(
                self, "确认",
                f"将分析 {len(audio_files)} 个音频文件，结果保存到：\n{csv_path}\n\n是否继续？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

            # 进度对话框
            self.lufs_progress_dialog = QProgressDialog("正在分析LUFS...", "取消", 0, 100, self)
            self.lufs_progress_dialog.setWindowTitle("LUFS分析")
            self.lufs_progress_dialog.setWindowModality(Qt.WindowModal)
            self.lufs_progress_dialog.setMinimumDuration(0)
            self.lufs_progress_dialog.show()

            # 启动线程
            self.lufs_thread = LufsAnalysisThread(audio_files, csv_path, self)
            self.lufs_thread.progress.connect(self.lufs_progress_dialog.setValue)
            self.lufs_thread.status.connect(self.lufs_progress_dialog.setLabelText)
            def on_finish(csv_path, failed_files):
                self.lufs_progress_dialog.close()
                msg = f"分析完成，结果已保存到：\n{csv_path}"
                if failed_files:
                    msg += "\n\n以下文件分析失败："
                    for  error in failed_files:
                        msg += f"{error}"
                self.show_long_message("分析完成", msg)
                folder = os.path.dirname(csv_path)
                if os.name == 'nt':
                    os.startfile(folder)
                elif os.name == 'posix':
                    os.system(f'open \"{folder}\"' if sys.platform == 'darwin' else f'xdg-open \"{folder}\"')
            def on_failed(msg):
                self.lufs_progress_dialog.close()
                if msg == "用户取消操作":
                    QMessageBox.information(self, "已取消", "LUFS分析已取消。")
                else:
                    QMessageBox.critical(self, "分析失败", msg)
            self.lufs_thread.finished_ok.connect(on_finish)
            self.lufs_thread.failed.connect(on_failed)
            self.lufs_progress_dialog.canceled.connect(self.lufs_thread.cancel)
            self.lufs_thread.start()

        def on_audio_files_failed(msg):
            self.audio_fetch_dialog.close()
            QMessageBox.critical(self, "获取音频对象失败", msg)

        self.audio_fetch_thread.finished_ok.connect(on_audio_files_ok)
        self.audio_fetch_thread.failed.connect(on_audio_files_failed)
        self.audio_fetch_dialog.canceled.connect(self.audio_fetch_thread.terminate)
        self.audio_fetch_thread.start()
    def open_loudness_report(self):
        # 保证窗口不会被垃圾回收
        if not hasattr(self, "_loudness_report_win") or self._loudness_report_win is None:
            self._loudness_report_win = show_loudness_report(self)
        else:
            self._loudness_report_win.show()
            self._loudness_report_win.raise_()
            self._loudness_report_win.activateWindow()









if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()  
    app = QApplication(sys.argv)
    try:
        window = Wreaper()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"应用程序崩溃: {traceback.format_exc()}")
        QMessageBox.critical(None, "应用程序错误", f"程序发生严重错误:\n{str(e)}\n\n详细信息请查看日志")