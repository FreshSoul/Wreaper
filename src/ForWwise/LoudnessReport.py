import sys
import socket
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QLabel, QHeaderView, QPushButton, QFileDialog,QMessageBox,QMenu
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QBrush
from waapi import WaapiClient, CannotConnectToWaapiException


class LoudnessSearchUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("响度报告")
        self.resize(1000, 650)
        self.layout = QVBoxLayout(self)
        self.highlighted_paths = set()
        self.csv_path = None

        # 搜索框和范围筛选
        filter_layout = QHBoxLayout()

        # 打开文件按钮
        self.open_btn = QPushButton("打开CSV", self)
        filter_layout.addWidget(self.open_btn)
        self.open_btn.clicked.connect(self.open_csv)

        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText("输入关键字搜索")
        filter_layout.addWidget(self.search_box)

        filter_layout.addWidget(QLabel("LUFS-I-Ingame范围:"))
        self.lufs_i_min = QLineEdit(self)
        self.lufs_i_min.setPlaceholderText("最小值")
        self.lufs_i_min.setFixedWidth(60)
        filter_layout.addWidget(self.lufs_i_min)
        filter_layout.addWidget(QLabel("~"))
        self.lufs_i_max = QLineEdit(self)
        self.lufs_i_max.setPlaceholderText("最大值")
        self.lufs_i_max.setFixedWidth(60)
        filter_layout.addWidget(self.lufs_i_max)

        filter_layout.addWidget(QLabel("LUFS-M-MAX-Ingame范围:"))
        self.lufs_m_min = QLineEdit(self)
        self.lufs_m_min.setPlaceholderText("最小值")
        self.lufs_m_min.setFixedWidth(60)
        filter_layout.addWidget(self.lufs_m_min)
        filter_layout.addWidget(QLabel("~"))
        self.lufs_m_max = QLineEdit(self)
        self.lufs_m_max.setPlaceholderText("最大值")
        self.lufs_m_max.setFixedWidth(60)
        filter_layout.addWidget(self.lufs_m_max)

        # 添加高亮按钮
        self.highlight_btn = QPushButton("标红", self)
        filter_layout.addWidget(self.highlight_btn)
        self.highlight_btn.clicked.connect(self.highlight_in_range_rows)

        # 添加搜索按钮
        self.search_btn = QPushButton("搜索", self)
        filter_layout.addWidget(self.search_btn)
        self.search_btn.clicked.connect(self.on_search)

        self.layout.addLayout(filter_layout)

        # 只保留一个表格控件
        self.table = QTableWidget(self)
        self.layout.addWidget(self.table)
        
        # 表格右键菜单：复制 wwise_path
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.on_table_context_menu)

        # 绑定回车事件
        self.search_box.returnPressed.connect(self.on_search)
        self.lufs_i_min.returnPressed.connect(self.on_search)
        self.lufs_i_max.returnPressed.connect(self.on_search)
        self.lufs_m_min.returnPressed.connect(self.on_search)
        self.lufs_m_max.returnPressed.connect(self.on_search)

        # 默认无数据
        self.df = pd.DataFrame(columns=["LUFS-I-Ingame", "LUFS-M-MAX-Ingame", "wwise_path"])
        self.show_data(self.df)

        # 表格设置...
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        font = QFont()
        font.setBold(True)
        self.table.horizontalHeader().setFont(font)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setShowGrid(True)
        self.table.setFont(QFont("微软雅黑", 10))
        self.table.cellDoubleClicked.connect(self.on_double_click)

    def open_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择CSV文件", "", "CSV Files (*.csv)")
        if file_path:
            self.csv_path = file_path
            try:
                df = pd.read_csv(file_path)
                # 自动检测列名
                for col in ["LUFS-I-Ingame", "LUFS-M-MAX-Ingame", "wwise_path"]:
                    if col not in df.columns:
                        raise Exception(f"缺少列: {col}")
                df = df[["LUFS-I-Ingame", "LUFS-M-MAX-Ingame", "wwise_path"]]
                df["LUFS-I-Ingame"] = df["LUFS-I-Ingame"].astype(float).round(1)
                df["LUFS-M-MAX-Ingame"] = df["LUFS-M-MAX-Ingame"].astype(float).round(1)
                self.df = df
                self.highlighted_paths.clear()
                self.show_data(self.df)
            except Exception as e:
                self.df = pd.DataFrame(columns=["LUFS-I-Ingame", "LUFS-M-MAX-Ingame", "wwise_path"])
                self.show_data(self.df)
                print("CSV读取失败：", e)
    def on_table_context_menu(self, pos):
        """表格右键菜单：在 wwise_path 列上右键可复制路径"""
        item = self.table.itemAt(pos)
        if not item:
            return

        row = item.row()
        col = item.column()
        if col != 2:  # 只在 wwise_path 列提供复制
            return

        path_item = self.table.item(row, 2)
        if not path_item:
            return
        wwise_path = path_item.text().strip()
        if not wwise_path:
            return

        menu = QMenu(self)
        act_copy = menu.addAction("复制路径")
        selected = menu.exec_(self.table.viewport().mapToGlobal(pos))
        if selected == act_copy:
            QApplication.clipboard().setText(wwise_path)

    def show_data(self, df):
        self.table.setRowCount(len(df))
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["LUFS-I-Ingame", "LUFS-M-Ingame", "wwise_path"])
        for row, (_, data) in enumerate(df.iterrows()):
            item0 = QTableWidgetItem(f"{data['LUFS-I-Ingame']:.1f}")
            item1 = QTableWidgetItem(f"{data['LUFS-M-MAX-Ingame']:.1f}")
            item2 = QTableWidgetItem(str(data['wwise_path']))
            item2.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item2.setToolTip(str(data['wwise_path']))
            self.table.setItem(row, 0, item0)
            self.table.setItem(row, 1, item1)
            self.table.setItem(row, 2, item2)
            # 如果该行wwise_path在高亮集合中，刷红色
            if str(data['wwise_path']) in self.highlighted_paths:
                for col in range(3):
                    self.table.item(row, col).setBackground(QBrush(QColor(255, 200, 200)))
            else:
                for col in range(3):
                    self.table.item(row, col).setBackground(QBrush(Qt.white))
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        self.table.resizeRowsToContents()

    def on_search(self, text=None):
        df = self.df
        keyword = self.search_box.text().strip().lower()
        if keyword:
            df = df[
                df.apply(lambda row: keyword in str(row["LUFS-I-Ingame"]).lower()
                                   or keyword in str(row["LUFS-M-MAX-Ingame"]).lower()
                                   or keyword in str(row["wwise_path"]).lower(), axis=1)
            ]
        try:
            lufs_i_min = float(self.lufs_i_min.text())
            df = df[df["LUFS-I-Ingame"] >= lufs_i_min]
        except ValueError:
            pass
        try:
            lufs_i_max = float(self.lufs_i_max.text())
            df = df[df["LUFS-I-Ingame"] <= lufs_i_max]
        except ValueError:
            pass
        try:
            lufs_m_min = float(self.lufs_m_min.text())
            df = df[df["LUFS-M-MAX-Ingame"] >= lufs_m_min]
        except ValueError:
            pass
        try:
            lufs_m_max = float(self.lufs_m_max.text())
            df = df[df["LUFS-M-MAX-Ingame"] <= lufs_m_max]
        except ValueError:
            pass
        self.show_data(df)

    def highlight_in_range_rows(self):
        # 如果已经有高亮，则取消所有高亮
        if self.highlighted_paths:
            self.highlighted_paths.clear()
            for row in range(self.table.rowCount()):
                for col in range(self.table.columnCount()):
                    self.table.item(row, col).setBackground(QBrush(Qt.white))
            return

        # 否则执行高亮
        try:
            lufs_i_min = float(self.lufs_i_min.text())
        except ValueError:
            lufs_i_min = None
        try:
            lufs_i_max = float(self.lufs_i_max.text())
        except ValueError:
            lufs_i_max = None
        try:
            lufs_m_min = float(self.lufs_m_min.text())
        except ValueError:
            lufs_m_min = None
        try:
            lufs_m_max = float(self.lufs_m_max.text())
        except ValueError:
            lufs_m_max = None

        for row in range(self.table.rowCount()):
            try:
                lufs_i = float(self.table.item(row, 0).text())
                lufs_m = float(self.table.item(row, 1).text())
                wwise_path = self.table.item(row, 2).text()
            except Exception:
                continue
            in_range = True
            if lufs_i_min is not None and lufs_i < lufs_i_min:
                in_range = False
            if lufs_i_max is not None and lufs_i > lufs_i_max:
                in_range = False
            if lufs_m_min is not None and lufs_m < lufs_m_min:
                in_range = False
            if lufs_m_max is not None and lufs_m > lufs_m_max:
                in_range = False
            if in_range:
                self.highlighted_paths.add(wwise_path)
                for col in range(self.table.columnCount()):
                    self.table.item(row, col).setBackground(QBrush(QColor(255, 200, 200)))
            else:
                for col in range(self.table.columnCount()):
                    self.table.item(row, col).setBackground(QBrush(Qt.white))

    def get_current_df(self):
        rows = []
        for row in range(self.table.rowCount()):
            lufs_i = float(self.table.item(row, 0).text())
            lufs_m = float(self.table.item(row, 1).text())
            wwise_path = self.table.item(row, 2).text()
            rows.append({"LUFS-I-Ingame": lufs_i, "LUFS-M-MAX-Ingame": lufs_m, "wwise_path": wwise_path})
        return pd.DataFrame(rows)

    def _is_waapi_port_open(self, host="127.0.0.1", port=8080, timeout=0.5):
        """快速探测 WAAPI 端口是否可用，避免阻塞或崩溃"""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    def on_double_click(self, row, col):
        item = self.table.item(row, 2)  # 第 3 列是 wwise_path
        if not item:
            return
        wwise_path = item.text().strip()
        if not wwise_path:
            return

        # 先检测 WAAPI 端口，未开就直接返回
        if not self._is_waapi_port_open():
            try:
                QMessageBox.warning(
                    self,
                    "WAAPI 未连接",
                    "未检测到 Wwise 的 WAAPI 端口（127.0.0.1:8080）。\n"
                    "请先在 Wwise 中启用 WAAPI 或打开 Wwise，然后再双击表格。"
                )
            except Exception:
                pass
            return
        try:
            try:
                with WaapiClient() as client:
                    result = client.call("ak.wwise.core.object.get", {
                        "from": {"path": [wwise_path]},
                        "options": {"return": ["id","parent"]}
                    })
                    # 这里统一处理“WWISE 中不存在该对象”的情况
                    if (not result) or ("return" not in result) or (not result["return"]):
                        try:
                            QMessageBox.information(
                                self,
                                "WWISE 中未找到对象",
                                f"当前 Wwise 工程中未找到此路径对应的对象：\n{wwise_path}"
                            )
                        except Exception:
                            pass
                        return

                    object_info = result["return"][0]
                    object_id = object_info.get("id")
                    parent_info = object_info.get("parent", {})
                    parent_id = parent_info.get("id")

                    if not object_id:
                        QMessageBox.information(
                            self,
                            "WWISE 中未找到对象",
                            f"返回结果中没有有效对象 ID：\n{wwise_path}"
                        )
                        return

                    # 正常操作
                    client.call("ak.wwise.ui.commands.execute", {
                        "command": "FindInProjectExplorerSelectionChannel1",
                        "objects": [object_id]
                    })
                    if parent_id:
                        client.call("ak.wwise.ui.commands.execute", {
                            "command": "OpenInNewTab",
                            "objects": [parent_id]
                        })
            except CannotConnectToWaapiException as e:
                QMessageBox.warning(self, "WAAPI 连接失败", str(e))
        except Exception as e:
            print("on_double_click异常：", e)
def show_loudness_report(parent=None):
    win = LoudnessSearchUI()
    # 不要 setParent，不要继承主窗口样式，只继承字体（可选）
    if parent:
        win.setFont(parent.font())
    win.show()
    return win

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = LoudnessSearchUI()
    win.show()
    sys.exit(app.exec_())
    
