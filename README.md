# Wreaper

<p align="center">
  <strong>Wwise + Reaper 音频工作流集成工具</strong>
</p>

<p align="center">
  <em>ALL FOR AUDIO</em>
</p>

Wreaper 是一个基于 PyQt5 构建的桌面应用，旨在打通 **Wwise** 与 **REAPER** 之间的工作流程，为游戏音频设计师提供高效的音频导入、渲染、响度分析等一站式解决方案。

---

## ✨ 功能特性

### 🔗 Wwise ↔ Reaper 互通

| 功能 | 说明 |
|------|------|
| **启动 Reaper** | 一键启动配置好的 REAPER 实例 |
| **导入 Reaper** | 将 Wwise 中选中的音频对象直接导入 REAPER |
| **所选 Item 渲染回 Wwise** | 将 REAPER 中选中的 Item 渲染并覆盖回 Wwise 原始文件，支持自定义采样率与通道数 |
| **区间导入 Reaper** | 将 Wwise 选中的多个音频按区间方式导入 REAPER，自动创建 Region |
| **区间渲染回 Wwise** | 按 REAPER Region 批量渲染并回写 Wwise |

### 📊 音频分析

| 功能 | 说明 |
|------|------|
| **2D 频谱分析** | 批量生成音频文件的 2D 频谱图（时间-频率-幅度） |
| **3D 频谱分析** | 生成三维频谱曲面图，适合可视化长音频 |
| **频谱质心分析** | 分析音频的频谱质心变化，评估音色亮度 |
| **响度数据（Wwise 项目）** | 基于 Wwise 项目层级结构，批量分析 LUFS-I / LUFS-M-MAX，并计算 In-game 等效响度 |
| **响度报告** | 可视化响度 CSV 数据，支持搜索、筛选、排序和高亮 |

### 🎚️ In-game 响度估算

响度分析会自动采集 Wwise 中的完整音量链路并计算 In-game 等效响度：

$$\text{LUFS-Ingame} = \text{LUFS} + \text{VolumeOffset} + \sum \text{AncestorVolumes} + \sum \text{AncestorMakeUpGains} + \sum \text{BusVolumes}$$

采集的数据包括：
- AudioFileSource 的 `VolumeOffset`
- 音频对象所有祖先层级的 `Volume` 和 `MakeUpGain`
- Output Bus 及其祖先的 `BusVolume` 和 `Volume`

### 🔄 自动更新

应用启动时自动检查 GitHub Releases 上的新版本，支持一键下载更新。

### 📋 响度报告

响度报告是一个独立的可视化窗口，用于查看和分析「响度数据」功能导出的 CSV 文件。

**数据展示**
- 以表格形式展示四列核心数据：**LUFS-I-Ingame**、**LUFS-M-Ingame**、**name**、**wwise_path**
- 数值列支持点击表头**排序**（升序/降序），快速定位最响或最安静的音频
- 首次加载自动适配列宽，支持手动调整

**搜索与筛选**
- **关键字搜索**：在名称、路径、数值中模糊匹配
- **LUFS-I 范围筛选**：设定 LUFS-I-Ingame 的最小值和最大值，过滤不在范围内的条目
- **LUFS-M 范围筛选**：同上，针对 LUFS-M-MAX-Ingame
- 支持组合使用：同时输入关键字 + 范围条件进行精确筛选

**颜色高亮**
- **按范围高亮**：设定 LUFS 范围后点击「设置颜色」，自动为范围内的所有行标记颜色
- **按行高亮**：右键选中行 →「设置行颜色」，为单行或多选行自定义颜色
- **清除颜色**：右键「清除行颜色」移除单行标记，或通过颜色对话框中的「取消所有颜色」一键清空
- 颜色标记在搜索/筛选后依然保留

**Wwise 联动**
- **双击行**自动连接 WAAPI，在 Wwise 中定位到对应对象：
  - 在 Project Explorer 中高亮选中该对象
  - 自动打开其父级对象的属性编辑页签
- 如果 Wwise 未启动或 WAAPI 端口未开启，会弹出友好提示
- 如果对象在当前 Wwise 工程中不存在，也会给出明确反馈

**右键菜单**
- **复制名称**：复制当前行的 name 到剪贴板
- **复制路径**：复制当前行的 wwise_path 到剪贴板

---

## 📁 项目结构

```
Wreaper/
├── version.txt                    # 版本号
├── src/
│   ├── WreaperRel.py              # 主程序入口（PyQt5 GUI）
│   ├── reaperconfig.txt           # Reaper 路径配置
│   ├── requirements.txt.txt       # Python 依赖
│   ├── wreaper.spec               # PyInstaller 打包配置
│   │
│   ├── backend/                   # 后端服务
│   │   ├── reaper_service.py      # Reaper 操作封装（启动、导入、渲染）
│   │   ├── wwise_service.py       # Wwise WAAPI 连接与操作
│   │   └── updater.py             # 版本检查与下载
│   │
│   ├── AudioAnalyse/              # 音频分析模块
│   │   ├── AudioAnalyse.py        # 频谱图生成（2D/3D/质心）
│   │   ├── AudioAnalysisThread.py # 分析后台线程（含 LUFS 多进程分析）
│   │   └── AnalyseLUFS_Game_Wwise.py  # LUFS 分析 + Wwise 音频源获取
│   │
│   ├── ForWwise/                  # Wwise 辅助工具
│   │   ├── AnalyseSelectMediaSource.py  # 选中对象的响度分析（独立脚本）
│   │   ├── AnalyseLUFS.py         # LUFS 分析核心
│   │   ├── GetAudioMediaSource.py # 获取音频源路径
│   │   ├── LoudnessReport.py      # 响度报告可视化 UI
│   │   ├── VolumeToMakeupGainForHDR.py  # Volume 转 MakeUpGain（HDR 工具）
│   │   ├── AudioSearch.py         # 音频网络搜索
│   │   └── WwiseHelp.py           # Wwise 辅助函数
│   │
│   └── utils/                     # 工具类
│       ├── config.py              # 应用配置（版本号、GitHub 信息等）
│       ├── download_thread.py     # 下载线程
│       ├── resources.py           # 资源路径处理
│       └── update_runner.py       # 更新替换与重启
```

---

## 🚀 快速开始

### 环境要求

- **Python** 3.8+
- **REAPER**（已安装并可运行）
- **Wwise**（已启用 WAAPI，默认端口 `8080`）



### 首次使用

1. 启动应用后，进入 **功能 → 配置 Reaper 启动路径**，选择 `reaper.exe` 所在位置
2. 确保 Wwise 已打开并启用 WAAPI（Edit → Preferences → Allow WAAPI Connections）
3. 在 Wwise 中选中音频对象，然后使用 Wreaper 的各项功能

---


## 🛠️ 技术栈

| 技术 | 用途 |
|------|------|
| **PyQt5** | GUI 框架 |
| **WAAPI (waapi-client)** | Wwise 自动化接口 |
| **reapy** | REAPER 脚本 API |
| **librosa / scipy** | 音频频谱分析 |
| **pyloudnorm** | LUFS 响度测量 |
| **matplotlib** | 频谱图可视化 |
| **pandas** | 响度报告数据处理 |


## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

- GitHub: [FreshSoul/Wreaper](https://github.com/FreshSoul/Wreaper)
