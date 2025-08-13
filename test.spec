import sys
import subprocess
import reapy
import psutil
import stat
import os
import tkinter as tk
from tkinter import filedialog
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, 
                            QMessageBox, QLabel, QHBoxLayout, QSpacerItem, 
                            QSizePolicy)
from PyQt5.QtGui import QPixmap, QFont, QIcon, QPalette, QBrush
from PyQt5.QtCore import Qt, QSize
from waapi import WaapiClient

CONFIG_FILE = 'reaperconfig.txt'

class Wreaper(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        
    def initUI(self):
        # 设置窗口背景图片
        self.set_background_image("background.jpg")  # 替换为你的图片路径
        
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # 顶部标题区域
        title_layout = QHBoxLayout()
        
        # 动漫风格图标
        self.logo_label = QLabel()
        # 这里应该替换为实际图片路径
        # 示例使用一个虚拟的动漫风格图标
        self.logo_label.setPixmap(QPixmap("anime_icon.png").scaled(80, 80, Qt.KeepAspectRatio))
        title_layout.addWidget(self.logo_label)
        
        # 标题文本
        title_text = QLabel("Wreaper")
        title_font = QFont()
        title_font.setFamily("Arial Rounded MT Bold")
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_text.setFont(title_font)
        title_text.setStyleSheet("color: #FF6B9E; background-color: rgba(255, 255, 255, 0.7); border-radius: 10px; padding: 5px;")
        title_layout.addWidget(title_text)
        
        # 添加弹性空间使标题居中
        title_layout.addStretch()
        main_layout.addLayout(title_layout)
        
        # 分隔线
        separator = QLabel()
        separator.setStyleSheet("background-color: rgba(255, 158, 183, 0.7); height: 2px;")
        separator.setFixedHeight(2)
        main_layout.addWidget(separator)
        
        # 按钮区域
        button_layout = QVBoxLayout()
        button_layout.setSpacing(15)
        
        # 按钮1 - 配置Reaper启动路径
        self.button1 = self.create_anime_button("配置Reaper启动路径", "#FF9EB7", "#FF6B9E")
        self.button1.clicked.connect(self.Select_reaperconfig)
        button_layout.addWidget(self.button1)
        
        # 按钮2 - 导入Reaper
        self.button2 = self.create_anime_button("导入Reaper", "#A2D5F2", "#5E9DD1")
        self.button2.clicked.connect(self.start_reaper_and_open_audio)
        button_layout.addWidget(self.button2)
        
        # 按钮3 - 渲染回Wwise
        self.button3 = self.create_anime_button("渲染回Wwise", "#A6E3A1", "#5DB85D")
        self.button3.clicked.connect(self.execute_rendering)
        button_layout.addWidget(self.button3)
        
        main_layout.addLayout(button_layout)
        
        # 底部状态区域
        status_layout = QHBoxLayout()
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("""
            color: white; 
            font-style: italic;
            background-color: rgba(0, 0, 0, 0.5);
            border-radius: 5px;
            padding: 3px;
        """)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        
        # 添加动漫风格的小图标
        anime_icon = QLabel()
        anime_icon.setPixmap(QPixmap("anime_small.png").scaled(30, 30, Qt.KeepAspectRatio))
        status_layout.addWidget(anime_icon)
        
        main_layout.addLayout(status_layout)
        
        self.setLayout(main_layout)
        self.setWindowTitle('Wreaper - 动漫风格音频工具')
        self.setWindowIcon(QIcon("anime_icon.png"))
        self.setGeometry(200, 200, 400, 450)
        
        # 设置窗口样式
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
    
    def set_background_image(self, image_path):
        """设置窗口背景图片"""
        palette = QPalette()
        pixmap = QPixmap(image_path)
        palette.setBrush(QPalette.Background, QBrush(pixmap.scaled(
            self.size(), 
            Qt.IgnoreAspectRatio, 
            Qt.SmoothTransformation
        )))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
    
    def resizeEvent(self, event):
        """窗口大小改变时重设背景图片"""
        self.set_background_image("background.jpg")  # 替换为你的图片路径
        super().resizeEvent(event)
    
    def create_anime_button(self, text, color1, color2):
        button = QPushButton(text)
        button.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 {color1}, stop:1 {color2});
                border-radius: 15px;
                padding: 15px;
                font-weight: bold;
                font-size: 16px;
                color: white;
                text-align: center;
                min-width: 200px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 {color1}, stop:1 {color2});
                border: 2px solid white;
                opacity: 0.9;
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                          stop:0 {color2}, stop:1 {color1});
                position: relative;
                top: 1px;
                left: 1px;
            }}
        """)
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedHeight(60)
        return button

    # ... (其余方法保持不变) ...

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle('Fusion')
    
    # 创建并显示主窗口
    ex = Wreaper()
    ex.show()
    
    sys.exit(app.exec_())