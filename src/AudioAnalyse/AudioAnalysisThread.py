
import os
from PyQt5.QtCore import  QThread, pyqtSignal
from AudioAnalyse import AudioAnalyse as audio_analysis
import csv
from concurrent.futures import ProcessPoolExecutor, as_completed
class AudioAnalysisThread(QThread):
    """音频分析后台线程"""
    progress = pyqtSignal(int)  # 进度信号 (0-100)
    status_update = pyqtSignal(str)  # 状态更新信号
    finished_ok = pyqtSignal(str)  # 成功完成信号
    failed = pyqtSignal(str)  # 失败信号

    def __init__(self, analysis_type, input_dir, output_dir, parent=None):
        super().__init__(parent)
        self.analysis_type = analysis_type  # "2d", "3d", "centroid"
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run(self):
        try:
            configs = {
                "2d": (
                    ('.wav', '.mp3', '.ogg', '.flac', '.m4a', '.aac'),
                    audio_analysis.plot_spectrogram_2d,
                    "正在处理",
                ),
                "3d": (
                    ('.wav', '.wave', '.aiff', '.flac'),
                    audio_analysis.plot_spectrogram_3d,
                    "正在生成3D频谱",
                ),
                "centroid": (
                    ('.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac'),
                    audio_analysis.analyze_audio_file_centroid,
                    "正在分析频谱质心",
                ),
            }
            formats, func, status_prefix = configs[self.analysis_type]
            self._run_batch_analysis(formats, func, status_prefix)
        except Exception as e:
            self.failed.emit(f"分析过程中出错：{str(e)}")

    def _run_batch_analysis(self, supported_formats, analysis_func, status_prefix):
        """通用批量分析逻辑"""
        audio_files = []
        for root, _, files in os.walk(self.input_dir):
            for file in files:
                if file.lower().endswith(supported_formats):
                    audio_files.append(os.path.join(root, file))

        if not audio_files:
            self.failed.emit("所选目录中没有找到支持的音频文件!")
            return

        os.makedirs(self.output_dir, exist_ok=True)

        success_count = 0
        error_messages = []
        total_files = len(audio_files)

        for i, audio_file in enumerate(audio_files):
            if self.cancelled:
                self.failed.emit("用户取消操作")
                return

            filename = os.path.basename(audio_file)
            self.status_update.emit(f"{status_prefix}: {filename}")

            success, result = analysis_func(audio_file, self.output_dir)
            if success:
                success_count += 1
            else:
                error_messages.append(result)

            self.progress.emit(int((i + 1) / total_files * 100))

        if error_messages:
            log_path = os.path.join(self.output_dir, "processing_errors.log")
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(error_messages))

        result_msg = f"处理完成!\n\n成功处理: {success_count} 个文件"
        if error_messages:
            result_msg += f"\n失败: {len(error_messages)} 个文件\n\n错误详情已保存到日志文件"

        self.finished_ok.emit(result_msg)


class LufsAnalysisThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished_ok = pyqtSignal(str, list)
    failed = pyqtSignal(str)

    def __init__(self, audio_files, csv_path, parent=None):
        super().__init__(parent)
        self.audio_files = audio_files
        self.csv_path = csv_path
        self._is_cancelled = False


    def cancel(self):
        self._is_cancelled = True

    @staticmethod
    def analyse_one(audio):
        from AudioAnalyse import AnalyseLUFS_Game_Wwise as lufs_game_wwise
        try:
            integrated, max_momentary, error = lufs_game_wwise.analyze_loudness_detailed(audio['file_path'])
            return (audio, integrated, max_momentary, error)
        except Exception as e:
            return (audio, None, None, str(e))

    

    def run(self):
        try:
            # 计算最大父级层数和Bus层级
            max_depth = 0
            max_bus_depth = 0
            for audio in self.audio_files:
                depth = len(audio.get("ancestors_list", []))
                if depth > max_depth:
                    max_depth = depth
                bus_depth = len(audio.get("OutputBus_ancestors_list", []))
                if bus_depth > max_bus_depth:
                    max_bus_depth = bus_depth

            # 基础列 + 音频对象层级列 + Bus层级列
            base_fields = [
                "name", "wwise_path", "file_path", "LUFS-I", "LUFS-M-MAX", "音频时长",
                "VolumeOffset", "OutPutBus_Name", "OutPutBus_BusVolume", "OutPutBus_Volume"
            ]
            bus_level_fields = []
            for i in range(1, max_bus_depth + 1):
                bus_level_fields.append(f"OutputBus父{i}名")
                bus_level_fields.append(f"Bus_BusVolume{i}")
                bus_level_fields.append(f"Bus_Volume{i}")
            level_fields = []
            for i in range(1, max_depth + 1):
                level_fields.append(f"父级名{i}")
                level_fields.append(f"父级音量{i}")
                level_fields.append(f"父级MakeUpGain{i}")
            
            fieldnames = ["LUFS-I-Ingame", "LUFS-M-MAX-Ingame"] + base_fields + bus_level_fields + level_fields

            results = []
            failed_files = []
            total = len(self.audio_files)
            finished = 0
            
            # 多进程并发分析
            with ProcessPoolExecutor(max_workers=8) as executor:
                # 提交所有任务
                future_to_audio = {
                    executor.submit(LufsAnalysisThread.analyse_one, audio): audio
                    for audio in self.audio_files
                }
                for future in as_completed(future_to_audio):
                    if self._is_cancelled:
                        self.failed.emit("用户取消操作")
                        return
                    audio, integrated, max_momentary, error = future.result()
                    idx = finished + 1
                    self.status.emit(f"分析({idx}/{total}): {audio['name']}")
                    if error or integrated is None:
                        failed_files.append((audio['file_path'], error or "未知错误"))
                    else:
                        # 组装row（和你原来的逻辑一致）
                        row = {
                            "name": audio['name'],
                            "wwise_path": audio['wwise_path'],
                            "file_path": audio['file_path'],
                            "LUFS-I": integrated,
                            "LUFS-M-MAX": max_momentary,
                            "音频时长": audio['duration'],
                            "VolumeOffset": ("" if audio.get('VolumeOffset') is None else audio['VolumeOffset']),
                            "OutPutBus_Name": audio.get('OutputBus_Name', ''),
                            "OutPutBus_BusVolume": ("" if audio.get('OutputBus_BusVolume') is None else audio['OutputBus_BusVolume']),
                            "OutPutBus_Volume": ("" if audio.get('OutputBus_Volume') is None else audio['OutputBus_Volume']),
                        }
                        # Bus层级
                        bus_ancestors = audio.get("OutputBus_ancestors_list", [])
                        busvol_sum = 0.0
                        for i in range(max_bus_depth):
                            name_key = f"OutputBus父{i+1}名"
                            busvol_key = f"Bus_BusVolume{i+1}"
                            vol_key = f"Bus_Volume{i+1}"
                            if i < len(bus_ancestors):
                                row[name_key] = bus_ancestors[i].get("name", "")
                                bv = bus_ancestors[i].get("bus_volume", None)
                                v = bus_ancestors[i].get("volume", None)
                                row[busvol_key] = bv if bv is not None else ""
                                row[vol_key] = v if v is not None else ""
                                for val in [bv, v]:
                                    try:
                                        busvol_sum += float(val)
                                    except (TypeError, ValueError):
                                        pass
                            else:
                                row[name_key] = ""
                                row[busvol_key] = ""
                                row[vol_key] = ""
                        # OutPutBus_BusVolume与OutPutBus_Volume
                        for key in ['OutputBus_BusVolume', 'OutputBus_Volume']:
                            val = audio.get(key, 0)
                            try:
                                busvol_sum += float(val)
                            except (TypeError, ValueError):
                                pass
                        # 音频对象层级
                        ancestors = audio.get("ancestors_list", [])
                        obj_sum = 0.0
                        for i in range(max_depth):
                            name_key = f"父级名{i+1}"
                            vol_key = f"父级音量{i+1}"
                            mug_key = f"父级MakeUpGain{i+1}"
                            if i < len(ancestors):
                                row[name_key] = ancestors[i].get("name", "")
                                v = ancestors[i].get("volume", None)
                                m = ancestors[i].get("makeup", None)
                                row[vol_key] = v if v is not None else ""
                                row[mug_key] = m if m is not None else ""
                                for val in [v, m]:
                                    try:
                                        obj_sum += float(val)
                                    except (TypeError, ValueError):
                                        pass
                            else:
                                row[name_key] = ""
                                row[vol_key] = ""
                                row[mug_key] = ""
                        # VolumeOffset（AudioFileSource 源级音量偏移）
                        vol_offset = 0.0
                        try:
                            vol_offset = float(audio.get('VolumeOffset', 0) or 0)
                        except (TypeError, ValueError):
                            vol_offset = 0.0
                        # 计算前两列
                        lufs_i_sum = (integrated if integrated is not None else 0) + busvol_sum + obj_sum + vol_offset
                        lufs_max_sum = (max_momentary if max_momentary is not None else 0) + busvol_sum + obj_sum + vol_offset
                        row = {
                            "LUFS-I-Ingame": lufs_i_sum,
                            "LUFS-M-MAX-Ingame": lufs_max_sum,
                            **row
                        }
                        results.append(row)
                    finished += 1
                    self.progress.emit(int(finished / total * 100))

            # 写入CSV
            with open(self.csv_path, "w", newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in results:
                    writer.writerow(row)
            self.finished_ok.emit(self.csv_path, failed_files)
        except Exception as e:
            self.failed.emit(str(e))