import sys
import socket
import re
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

        # 主布局：增加边距与间距
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(12)

        self.highlighted_paths = {}          # 路径 -> 行高亮颜色
        self.highlight_color = QColor(255, 200, 200)
        self.sync_highlight_paths = set()    # 本次同步变更路径
        self.sync_highlight_color = QColor(180, 220, 255)  # 同步变更行蓝色
        self.csv_path = None
        self._name_col_auto_sized = False
        self._path_col_auto_sized = False

        # 搜索框和范围筛选
        self.filter_layout = QHBoxLayout()
        self.filter_layout.setSpacing(8)

        # 打开文件按钮
        self.open_btn = QPushButton("打开CSV", self)
        self.filter_layout.addWidget(self.open_btn)
        self.open_btn.clicked.connect(self.open_csv)

        self.sync_btn = QPushButton("同步", self)
        self.filter_layout.addWidget(self.sync_btn)
        self.sync_btn.clicked.connect(self.sync_wwise_volume_to_csv)

        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText("输入关键字搜索")
        self.filter_layout.addWidget(self.search_box)

        self.filter_layout.addWidget(QLabel("LUFS-I范围:"))
        self.lufs_i_min = QLineEdit(self)
        self.lufs_i_min.setPlaceholderText("最小值")
        self.lufs_i_min.setFixedWidth(60)
        self.filter_layout.addWidget(self.lufs_i_min)
        self.filter_layout.addWidget(QLabel("~"))
        self.lufs_i_max = QLineEdit(self)
        self.lufs_i_max.setPlaceholderText("最大值")
        self.lufs_i_max.setFixedWidth(60)
        self.filter_layout.addWidget(self.lufs_i_max)

        self.filter_layout.addWidget(QLabel("LUFS-M范围:"))
        self.lufs_m_min = QLineEdit(self)
        self.lufs_m_min.setPlaceholderText("最小值")
        self.lufs_m_min.setFixedWidth(60)
        self.filter_layout.addWidget(self.lufs_m_min)
        self.filter_layout.addWidget(QLabel("~"))
        self.lufs_m_max = QLineEdit(self)
        self.lufs_m_max.setPlaceholderText("最大值")
        self.lufs_m_max.setFixedWidth(60)
        self.filter_layout.addWidget(self.lufs_m_max)

        # 高亮按钮
        self.highlight_btn = QPushButton("设置颜色", self)
        self.filter_layout.addWidget(self.highlight_btn)
        self.highlight_btn.clicked.connect(self.highlight_in_range_rows)

        # 搜索按钮
        self.search_btn = QPushButton("搜索", self)
        self.filter_layout.addWidget(self.search_btn)
        self.search_btn.clicked.connect(self.on_search)

        self.layout.addLayout(self.filter_layout)

        
        self.table = QTableWidget(self)
        self.layout.addWidget(self.table)
        
        # 右键菜单：复制 wwise_path
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.on_table_context_menu)

        # 回车事件
        self.search_box.returnPressed.connect(self.on_search)
        self.lufs_i_min.returnPressed.connect(self.on_search)
        self.lufs_i_max.returnPressed.connect(self.on_search)
        self.lufs_m_min.returnPressed.connect(self.on_search)
        self.lufs_m_max.returnPressed.connect(self.on_search)

        # 默认无数据
        self.df = pd.DataFrame(columns=["LUFS-I-Ingame", "LUFS-M-MAX-Ingame", "name", "wwise_path"])
        self.show_data(self.df)

        # 表格设置
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

        
        self._apply_apple_style()

    def _apply_apple_style(self):
        
        # 基础字体
        base_font = QFont("SF Pro Display", 10)
        if not base_font.exactMatch():
            base_font = QFont("Segoe UI", 10)
        if not base_font.exactMatch():
            base_font = QFont("微软雅黑", 10)
        self.setFont(base_font)

        # 统一关闭明显的表格网格线
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)

        self.setStyleSheet("""
        QWidget {
            background-color: #f5f5f7;
            color: #1d1d1f;
            font-size: 13px;
        }

        QLineEdit {
            border-radius: 6px;
            padding: 4px 8px;
            border: 1px solid #d2d2d7;
            background-color: #ffffff;
        }
        QLineEdit:focus {
            border: 1px solid #007aff;
            background-color: #ffffff;
        }

        QLabel {
            color: #3a3a3c;
        }

        QPushButton {
            border-radius: 8px;
            padding: 6px 14px;
            border: none;
            background-color: #007aff;
            color: #ffffff;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: #1580ff;
        }
        QPushButton:pressed {
            background-color: #0060df;
        }
        QPushButton:disabled {
            background-color: #c7c7cc;
            color: #ffffff;
        }

        QTableWidget {
            background-color: #ffffff;
            border-radius: 10px;
            border: 1px solid #d2d2d7;
            gridline-color: #e5e5ea;
            selection-background-color: #d0e3ff;
            selection-color: #1d1d1f;
        }

        QHeaderView::section {
            background-color: #f5f5f7;
            color: #1d1d1f;
            border: none;
            border-bottom: 1px solid #d2d2d7;
            padding: 6px 8px;
            font-weight: 600;
        }

        QTableCornerButton::section {
            background-color: #f5f5f7;
            border: none;
            border-bottom: 1px solid #d2d2d7;
            border-right: 1px solid #d2d2d7;
        }

        QScrollBar:vertical {
            background: transparent;
            width: 10px;
            margin: 4px 2px 4px 0;
        }
        QScrollBar::handle:vertical {
            background: rgba(0,0,0,0.25);
            border-radius: 5px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover {
            background: rgba(0,0,0,0.35);
        }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            height: 0;
        }

        QScrollBar:horizontal {
            background: transparent;
            height: 10px;
            margin: 0 4px 2px 4px;
        }
        QScrollBar::handle:horizontal {
            background: rgba(0,0,0,0.25);
            border-radius: 5px;
            min-width: 20px;
        }
        QScrollBar::handle:horizontal:hover {
            background: rgba(0,0,0,0.35);
        }
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {
            width: 0;
        }
        """)
    
    def open_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择CSV文件", "", "CSV Files (*.csv)")
        if file_path:
            self._load_report_view(file_path)

    def _load_report_view(self, file_path):
        """加载CSV到报告表格。"""
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
            self.sync_highlight_paths.clear()
            self._name_col_auto_sized = False
            self._path_col_auto_sized = False
            self.show_data(self.df)
        except Exception as e:
            self.df = pd.DataFrame(columns=["LUFS-I-Ingame", "LUFS-M-MAX-Ingame", "name", "wwise_path"])
            self.show_data(self.df)
            print("CSV读取失败：", e)

    @staticmethod
    def _to_float(val, default=0.0):
        try:
            if pd.isna(val):
                return default
            return float(val)
        except Exception:
            return default

    @staticmethod
    def _ensure_column(df, col_name):
        if col_name not in df.columns:
            df[col_name] = ""

    @staticmethod
    def _extract_max_index(columns, pattern):
        max_idx = 0
        regex = re.compile(pattern)
        for col in columns:
            m = regex.fullmatch(col)
            if m:
                max_idx = max(max_idx, int(m.group(1)))
        return max_idx

    def _fetch_volume_state_by_path(self, client, wwise_path):
        """按对象路径读取当前Wwise音量层级信息。"""
        def _resolve_ref_to_id(ref):
            """把 WAAPI 返回的引用（dict/id/path）尽量解析成对象 id。"""
            if not ref:
                return None
            if isinstance(ref, dict):
                if ref.get("id"):
                    return ref.get("id")
                if ref.get("path"):
                    ref = ref.get("path")
                else:
                    return None

            if isinstance(ref, str):
                # GUID 形式
                if ref.startswith("{") and ref.endswith("}"):
                    return ref
                # path 形式
                try:
                    got = client.call("ak.wwise.core.object.get", {
                        "from": {"path": [ref]},
                        "options": {"return": ["id"]}
                    })
                    items = (got or {}).get("return", [])
                    if items:
                        return items[0].get("id")
                except Exception:
                    return None
            return None

        obj_info = client.call("ak.wwise.core.object.get", {
            "from": {"path": [wwise_path]},
            "options": {"return": ["id", "name", "type", "path", "parent", "@VolumeOffset", "OutputBus", "@OutputBus"]}
        })
        obj_items = (obj_info or {}).get("return", [])
        if not obj_items:
            return None

        obj = obj_items[0]
        object_id = obj.get("id")
        if not object_id:
            return None

        # 先从对象自身取 OutputBus
        bus_id = _resolve_ref_to_id(obj.get("OutputBus")) or _resolve_ref_to_id(obj.get("@OutputBus"))

        # 再尝试从父对象取
        if not bus_id:
            parent_ref = obj.get("parent")
            parent_id = _resolve_ref_to_id(parent_ref)
            if parent_id:
                parent_info = client.call("ak.wwise.core.object.get", {
                    "from": {"id": [parent_id]},
                    "options": {"return": ["id", "OutputBus", "@OutputBus"]}
                })
                parent_items = (parent_info or {}).get("return", [])
                if parent_items:
                    parent_obj = parent_items[0]
                    bus_id = _resolve_ref_to_id(parent_obj.get("OutputBus")) or _resolve_ref_to_id(parent_obj.get("@OutputBus"))

        ancestors_info = client.call("ak.wwise.core.object.get", {
            "from": {"id": [object_id]},
            "transform": [{"select": ["ancestors"]}],
            "options": {"return": ["id", "name", "@Volume", "@MakeUpGain", "OutputBus", "@OutputBus"]}
        })
        raw_ancestors = (ancestors_info or {}).get("return", [])

        ancestors_list = []
        for anc in raw_ancestors:
            anc_name = anc.get("name")
            if anc_name:
                ancestors_list.append({
                    "name": anc_name,
                    "volume": anc.get("@Volume"),
                    "makeup": anc.get("@MakeUpGain")
                })

        # 对象未设 OutputBus 时，沿祖先找第一个设置的
        if not bus_id:
            for anc in raw_ancestors:
                anc_bus_id = _resolve_ref_to_id(anc.get("OutputBus")) or _resolve_ref_to_id(anc.get("@OutputBus"))
                if anc_bus_id:
                    bus_id = anc_bus_id
                    break

        bus_name = ""
        bus_bus_volume = None
        bus_volume = None
        bus_ancestors_list = []

        if bus_id:
            bus_info = client.call("ak.wwise.core.object.get", {
                "from": {"id": [bus_id]},
                "options": {"return": ["id", "name", "@BusVolume", "@Volume"]}
            })
            bus_items = (bus_info or {}).get("return", [])
            if bus_items:
                bus_name = bus_items[0].get("name", "")
                bus_bus_volume = bus_items[0].get("@BusVolume")
                bus_volume = bus_items[0].get("@Volume")

            bus_ancestors_info = client.call("ak.wwise.core.object.get", {
                "from": {"id": [bus_id]},
                "transform": [{"select": ["ancestors"]}],
                "options": {"return": ["id", "name", "@BusVolume", "@Volume"]}
            })
            raw_bus_ancestors = (bus_ancestors_info or {}).get("return", [])
            for anc in raw_bus_ancestors:
                bus_ancestors_list.append({
                    "name": anc.get("name", ""),
                    "bus_volume": anc.get("@BusVolume"),
                    "volume": anc.get("@Volume")
                })

        return {
            "VolumeOffset": obj.get("@VolumeOffset"),
            "OutPutBus_Name": bus_name,
            "OutPutBus_BusVolume": bus_bus_volume,
            "OutPutBus_Volume": bus_volume,
            "ancestors_list": ancestors_list,
            "bus_ancestors_list": bus_ancestors_list,
        }

    def sync_wwise_volume_to_csv(self):
        """把Wwise当前音量层级同步到CSV（仅写回有变化的行），并增量刷新响度报告。"""
        if not self.csv_path:
            QMessageBox.information(self, "提示", "请先打开一个CSV文件。")
            return

        # 每次同步先清掉上次同步蓝色标记
        self.sync_highlight_paths.clear()
        self._apply_backgrounds()

        if not self._is_waapi_port_open():
            QMessageBox.warning(self, "WAAPI 未连接", "请先启动Wwise并启用WAAPI。")
            return

        try:
            df_full = pd.read_csv(self.csv_path, low_memory=False)
        except Exception as e:
            QMessageBox.warning(self, "读取失败", f"无法读取CSV：{e}")
            return

        required_cols = ["wwise_path", "LUFS-I", "LUFS-M-MAX"]
        missing = [c for c in required_cols if c not in df_full.columns]
        if missing:
            QMessageBox.warning(
                self,
                "CSV列不足",
                "当前CSV缺少必要列：" + ", ".join(missing) + "\n请使用Wreaper导出的完整LUFS CSV。"
            )
            return

        old_max_obj_depth = self._extract_max_index(df_full.columns, r"父级名(\d+)")
        old_max_bus_depth = self._extract_max_index(df_full.columns, r"OutputBus父(\d+)名")

        scanned = 0
        changed = 0
        failed = 0
        fail_paths = []
        changed_paths = []
        changed_values = {}

        def _same(a, b):
            # 空值判等
            if (pd.isna(a) or a == "") and (pd.isna(b) or b == ""):
                return True
            # 数值判等
            try:
                fa = float(a)
                fb = float(b)
                return abs(fa - fb) < 1e-9
            except Exception:
                pass
            # 字符串判等
            return str(a) == str(b)

        def _apply_if_changed(idx, updates):
            row_changed = False
            for k, v in updates.items():
                if k not in df_full.columns:
                    df_full[k] = ""
                old_v = df_full.at[idx, k] if k in df_full.columns else ""
                if not _same(old_v, v):
                    df_full.at[idx, k] = v
                    row_changed = True
            return row_changed

        try:
            with WaapiClient() as client:
                for idx, row in df_full.iterrows():
                    wwise_path = str(row.get("wwise_path", "")).strip()
                    if not wwise_path:
                        failed += 1
                        continue

                    scanned += 1

                    state = self._fetch_volume_state_by_path(client, wwise_path)
                    if not state:
                        failed += 1
                        fail_paths.append(wwise_path)
                        continue

                    ancestors = state["ancestors_list"]
                    bus_ancestors = state["bus_ancestors_list"]

                    updates = {
                        "VolumeOffset": "" if state["VolumeOffset"] is None else state["VolumeOffset"],
                        "OutPutBus_Name": state["OutPutBus_Name"],
                        "OutPutBus_BusVolume": "" if state["OutPutBus_BusVolume"] is None else state["OutPutBus_BusVolume"],
                        "OutPutBus_Volume": "" if state["OutPutBus_Volume"] is None else state["OutPutBus_Volume"],
                    }

                    # 对象祖先层级列
                    obj_sum = 0.0
                    for i, anc in enumerate(ancestors, start=1):
                        name_key = f"父级名{i}"
                        vol_key = f"父级音量{i}"
                        mug_key = f"父级MakeUpGain{i}"

                        v = anc.get("volume")
                        m = anc.get("makeup")
                        updates[name_key] = anc.get("name", "")
                        updates[vol_key] = "" if v is None else v
                        updates[mug_key] = "" if m is None else m
                        obj_sum += self._to_float(v, 0.0) + self._to_float(m, 0.0)

                    # 清理旧层级残留（对象）
                    target_obj_depth = max(old_max_obj_depth, len(ancestors))
                    for i in range(len(ancestors) + 1, target_obj_depth + 1):
                        updates[f"父级名{i}"] = ""
                        updates[f"父级音量{i}"] = ""
                        updates[f"父级MakeUpGain{i}"] = ""

                    # Bus祖先层级列
                    bus_sum = 0.0
                    for i, anc in enumerate(bus_ancestors, start=1):
                        name_key = f"OutputBus父{i}名"
                        bvol_key = f"Bus_BusVolume{i}"
                        vol_key = f"Bus_Volume{i}"

                        bv = anc.get("bus_volume")
                        v = anc.get("volume")
                        updates[name_key] = anc.get("name", "")
                        updates[bvol_key] = "" if bv is None else bv
                        updates[vol_key] = "" if v is None else v
                        bus_sum += self._to_float(bv, 0.0) + self._to_float(v, 0.0)

                    # 清理旧层级残留（Bus）
                    target_bus_depth = max(old_max_bus_depth, len(bus_ancestors))
                    for i in range(len(bus_ancestors) + 1, target_bus_depth + 1):
                        updates[f"OutputBus父{i}名"] = ""
                        updates[f"Bus_BusVolume{i}"] = ""
                        updates[f"Bus_Volume{i}"] = ""

                    # 计算Ingame列（按当前Wwise音量重新计算）
                    base_i = self._to_float(row.get("LUFS-I"), 0.0)
                    base_m = self._to_float(row.get("LUFS-M-MAX"), 0.0)
                    vol_offset = self._to_float(state["VolumeOffset"], 0.0)
                    bus_self = self._to_float(state["OutPutBus_BusVolume"], 0.0) + self._to_float(state["OutPutBus_Volume"], 0.0)

                    new_i = base_i + obj_sum + bus_sum + bus_self + vol_offset
                    new_m = base_m + obj_sum + bus_sum + bus_self + vol_offset
                    updates["LUFS-I-Ingame"] = new_i
                    updates["LUFS-M-MAX-Ingame"] = new_m

                    if _apply_if_changed(idx, updates):
                        changed += 1
                        changed_paths.append(wwise_path)
                        changed_values[wwise_path] = (new_i, new_m)

        except CannotConnectToWaapiException as e:
            QMessageBox.warning(self, "WAAPI 连接失败", str(e))
            return
        except Exception as e:
            QMessageBox.warning(self, "同步失败", f"同步过程中出错：{e}")
            return

        if changed == 0:
            self._apply_backgrounds()  # 确保清除旧蓝色后刷新UI
            QMessageBox.information(self, "同步完成", f"扫描 {scanned} 条，未发现变更。")
            return

        try:
            df_full.to_csv(self.csv_path, index=False, encoding="utf-8-sig")
        except Exception as e:
            QMessageBox.warning(self, "保存失败", f"写入CSV失败：{e}")
            return

        # 增量刷新当前表格
        changed_set = set(changed_paths)
        # 本次同步变更行标蓝
        self.sync_highlight_paths = changed_set

        # 同步更新内存中的 self.df，避免搜索/筛选后显示旧数据
        for wwise_path, (new_i, new_m) in changed_values.items():
            mask = self.df["wwise_path"].astype(str).str.strip() == wwise_path
            if mask.any():
                self.df.loc[mask, "LUFS-I-Ingame"] = new_i
                self.df.loc[mask, "LUFS-M-MAX-Ingame"] = new_m

        if not self.df.empty and changed_set:
            for r in range(self.table.rowCount()):
                path_item = self.table.item(r, 3)
                if not path_item:
                    continue
                p = path_item.text().strip()
                if p not in changed_set:
                    continue

                vals = changed_values.get(p)
                if not vals:
                    continue
                new_i, new_m = vals

                self.table.setItem(r, 0, NumericItem(new_i))
                self.table.setItem(r, 1, NumericItem(new_m))

        # 统一重绘背景（应用本次同步蓝色）——无论是否有变更都执行
        self._apply_backgrounds()

        if failed > 0:
            tail = ""
            if fail_paths:
                preview = "\n".join(fail_paths[:5])
                tail = f"\n\n未匹配对象示例（最多5条）：\n{preview}"
            QMessageBox.information(
                self,
                "同步完成",
                f"已变更同步 {changed} 条，失败 {failed} 条。{tail}"
            )
        else:
            QMessageBox.information(self, "同步完成", f"已变更同步 {changed} 条。")

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
            path = path_item.text().strip() if path_item else ""
            # 优先显示“本次同步变更”的蓝色
            if path in self.sync_highlight_paths:
                row_color = self.sync_highlight_color
            else:
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
                wwise_path = self.table.item(row, 3).text().strip()
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
    
