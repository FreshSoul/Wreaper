import sys
import socket
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QLabel, QHeaderView, QPushButton, QFileDialog,QMessageBox,QMenu,
    QColorDialog, QDialog  
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QBrush
from waapi import WaapiClient, CannotConnectToWaapiException


class NumericItem(QTableWidgetItem):
    """用于数字排序的表格项：按数值排序，文本显示保留两位小数"""
    def __init__(self, value: float):
        self._value = float(value)
        super().__init__(f"{self._value:.2f}")

    def __lt__(self, other):
        if isinstance(other, NumericItem):
            return self._value < other._value
        return super().__lt__(other)


class LoudnessSearchUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("响度报告")
        self.resize(1000, 650)
        self.layout = QVBoxLayout(self)
        self.highlighted_paths = {}          # 路径 -> 行高亮颜色
        self.highlight_color = QColor(255, 200, 200)
        self.csv_path = None
        self._name_col_auto_sized = False
        self._path_col_auto_sized = False
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
        self.highlight_btn = QPushButton("设置颜色", self)
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
        self.df = pd.DataFrame(columns=["LUFS-I-Ingame", "LUFS-M-MAX-Ingame", "name", "wwise_path"])
        self.show_data(self.df)

        # 表格设置...
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        

        header = self.table.horizontalHeader()
        for i in range(4):
            header.setSectionResizeMode(i, QHeaderView.Interactive)

        font = QFont()
        font.setBold(True)
        
        
        
        
        self.table.horizontalHeader().setFont(font)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setShowGrid(True)
        self.table.setFont(QFont("微软雅黑", 10))
        self.table.cellDoubleClicked.connect(self.on_double_click)

    def open_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择CSV文件", "", "CSV Files (*.csv)")
        if file_path:
            self.csv_path = file_path
            try:
                # 只读取需要的 4 列，并显式指定类型，关闭 low_memory 分块推断
                df = pd.read_csv(
                    file_path,
                    usecols=["LUFS-I-Ingame", "LUFS-M-MAX-Ingame", "name", "wwise_path"],
                    dtype={
                        "LUFS-I-Ingame": "float64",
                        "LUFS-M-MAX-Ingame": "float64",
                        "name": "string",
                        "wwise_path": "string",
                    },
                    low_memory=False,
                )

                df["LUFS-I-Ingame"] = df["LUFS-I-Ingame"].astype(float)
                df["LUFS-M-MAX-Ingame"] = df["LUFS-M-MAX-Ingame"].astype(float)

                self.df = df
                self.highlighted_paths.clear()
                self._name_col_auto_sized = False
                self._path_col_auto_sized = False
                self.show_data(self.df)
            except Exception as e:
                self.df = pd.DataFrame(columns=["LUFS-I-Ingame", "LUFS-M-MAX-Ingame", "name", "wwise_path"])
                self.show_data(self.df)
                print("CSV读取失败：", e)
    def on_table_context_menu(self, pos):
        """表格右键菜单：复制 name / 路径，或为选中行设置颜色"""
        item = self.table.itemAt(pos)
        if not item:
            return

        click_row = item.row()
        name_item = self.table.item(click_row, 2)
        path_item = self.table.item(click_row, 3)

        name = name_item.text().strip() if name_item else ""
        wwise_path = path_item.text().strip() if path_item else ""

        if not (name or wwise_path):
            return

        # 当前选中的所有行；如果没有选中，则只操作点击这一行
        selected_indexes = self.table.selectionModel().selectedRows()
        if selected_indexes:
            target_rows = [idx.row() for idx in selected_indexes]
        else:
            target_rows = [click_row]

        menu = QMenu(self)
        act_copy_name = act_copy_path = None

        if name:
            act_copy_name = menu.addAction("复制名称")
        if wwise_path:
            act_copy_path = menu.addAction("复制路径")

        if menu.actions():
            menu.addSeparator()

        # 文案改为“设置行颜色”
        act_color_row = menu.addAction("设置行颜色")
        act_clear_row = menu.addAction("清除行颜色")

        selected = menu.exec_(self.table.viewport().mapToGlobal(pos))
        if not selected:
            return

        clipboard = QApplication.clipboard()

        if selected == act_copy_name:
            clipboard.setText(name)
        elif selected == act_copy_path:
            clipboard.setText(wwise_path)
        elif selected == act_color_row:
            # 以点击行的已有颜色或默认颜色作为初始值
            base_color = self.highlighted_paths.get(wwise_path, self.highlight_color)
            dlg = QColorDialog(base_color, self)
            if dlg.exec_() == QDialog.Accepted:
                color = dlg.currentColor()
                if color.isValid():
                    for r in target_rows:
                        path_item = self.table.item(r, 3)
                        if not path_item:
                            continue
                        path = path_item.text().strip()
                        if path:
                            self.highlighted_paths[path] = color
                    self._apply_backgrounds()
        elif selected == act_clear_row:
            for r in target_rows:
                path_item = self.table.item(r, 3)
                if not path_item:
                    continue
                path = path_item.text().strip()
                if path:
                    self.highlighted_paths.pop(path, None)
            self._apply_backgrounds()

    def show_data(self, df):
        # 记住当前排序状态
        sort_enabled = self.table.isSortingEnabled()
        header = self.table.horizontalHeader()
        sort_col = header.sortIndicatorSection()
        sort_order = header.sortIndicatorOrder()

        self.table.setSortingEnabled(False)
        self.table.clearContents()
        self.table.setRowCount(len(df))
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["LUFS-I-Ingame", "LUFS-M-Ingame", "name", "wwise_path"]
        )

        for row, (_, data) in enumerate(df.iterrows()):
            lufs_i = float(data["LUFS-I-Ingame"])
            lufs_m = float(data["LUFS-M-MAX-Ingame"])
            name   = str(data["name"])
            path   = str(data["wwise_path"])

            item0 = NumericItem(lufs_i)
            item1 = NumericItem(lufs_m)

            item2 = QTableWidgetItem(name)
            item2.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item2.setToolTip(name)

            item3 = QTableWidgetItem(path)
            item3.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item3.setToolTip(path)

            self.table.setItem(row, 0, item0)
            self.table.setItem(row, 1, item1)
            self.table.setItem(row, 2, item2)
            self.table.setItem(row, 3, item3)
                # 仅第一次载入数据时，让 name 和 wwise_path 列按内容自动调宽
        if len(df) > 0:
            if not self._name_col_auto_sized:
                self.table.resizeColumnToContents(2)  # name
                self._name_col_auto_sized = True
            if not self._path_col_auto_sized:
                self.table.resizeColumnToContents(3)  # wwise_path
                self._path_col_auto_sized = True


        self.table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
  

        # 统一根据行/列配置刷新背景色
        self._apply_backgrounds()

        self.table.setSortingEnabled(sort_enabled)
        if sort_enabled and sort_col >= 0:
            self.table.sortItems(sort_col, sort_order)


    def _apply_backgrounds(self):
        """根据每行配置的颜色刷新背景色"""
        for row in range(self.table.rowCount()):
            path_item = self.table.item(row, 3)
            path = path_item.text() if path_item else ""
            row_color = self.highlighted_paths.get(path)

            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if not item:
                    continue
                color = row_color or Qt.white
                item.setBackground(QBrush(color))
    
    

    def on_search(self, text=None):
        df = self.df

        keyword = self.search_box.text().strip().lower()
        has_keyword = bool(keyword)

        # 先拿到原始文本，后面再转 float
        i_min_txt = self.lufs_i_min.text().strip()
        i_max_txt = self.lufs_i_max.text().strip()
        m_min_txt = self.lufs_m_min.text().strip()
        m_max_txt = self.lufs_m_max.text().strip()

        if not (has_keyword or i_min_txt or i_max_txt or m_min_txt or m_max_txt):
            self.show_data(self.df)
            return

        if has_keyword:
            df = df[
                df.apply(
                    lambda row: keyword in str(row["LUFS-I-Ingame"]).lower()
                    or keyword in str(row["LUFS-M-MAX-Ingame"]).lower()
                    or keyword in str(row["name"]).lower()
                    or keyword in str(row["wwise_path"]).lower(),
                    axis=1,
                )
            ]

        try:
            lufs_i_min = float(i_min_txt)
            df = df[df["LUFS-I-Ingame"] >= lufs_i_min]
        except ValueError:
            pass
        try:
            lufs_i_max = float(i_max_txt)
            df = df[df["LUFS-I-Ingame"] <= lufs_i_max]
        except ValueError:
            pass
        try:
            lufs_m_min = float(m_min_txt)
            df = df[df["LUFS-M-MAX-Ingame"] >= lufs_m_min]
        except ValueError:
            pass
        try:
            lufs_m_max = float(m_max_txt)
            df = df[df["LUFS-M-MAX-Ingame"] <= lufs_m_max]
        except ValueError:
            pass

        self.show_data(df)
    def highlight_in_range_rows(self):
        # 弹出颜色盘，并加入“取消所有颜色”按钮
        dialog = QColorDialog(self.highlight_color, self)
        clear_all = {"flag": False}

        btn_clear = QPushButton("取消所有颜色", dialog)
        dialog.layout().addWidget(btn_clear)

        def on_clear():
            clear_all["flag"] = True
            dialog.accept()

        btn_clear.clicked.connect(on_clear)

        if dialog.exec_() != QDialog.Accepted:
            return

        if clear_all["flag"]:
            self.highlighted_paths.clear()
            self._apply_backgrounds()
            return

        color = dialog.currentColor()
        if not color.isValid():
            return
        self.highlight_color = color

        # 读取范围
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

        # 只更新字典，让 _apply_backgrounds 统一上色
        for row in range(self.table.rowCount()):
            try:
                lufs_i = float(self.table.item(row, 0).text())
                lufs_m = float(self.table.item(row, 1).text())
                wwise_path = self.table.item(row, 3).text()
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
                self.highlighted_paths[wwise_path] = color

        self._apply_backgrounds()
        
    def get_current_df(self):
        rows = []
        for row in range(self.table.rowCount()):
            lufs_i = float(self.table.item(row, 0).text())
            lufs_m = float(self.table.item(row, 1).text())
            name = self.table.item(row, 2).text()
            wwise_path = self.table.item(row, 3).text()
            rows.append({
                "LUFS-I-Ingame": lufs_i,
                "LUFS-M-MAX-Ingame": lufs_m,
                "name": name,
                "wwise_path": wwise_path
            })
        return pd.DataFrame(rows)

    def _is_waapi_port_open(self, host="127.0.0.1", port=8080, timeout=0.5):
        """快速探测 WAAPI 端口是否可用，避免阻塞或崩溃"""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    def on_double_click(self, row, col):
        item = self.table.item(row, 3)  # 第 3 列是 wwise_path
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
    
