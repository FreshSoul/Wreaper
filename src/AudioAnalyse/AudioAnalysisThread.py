
import os
from PyQt5.QtCore import  QThread, pyqtSignal
from AudioAnalyse import AudioAnalyse as audio_analysis

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
            if self.analysis_type == "2d":
                self._run_2d_analysis()
            elif self.analysis_type == "3d":
                self._run_3d_analysis()
            elif self.analysis_type == "centroid":
                self._run_centroid_analysis()
        except Exception as e:
            self.failed.emit(f"分析过程中出错：{str(e)}")

    def _run_2d_analysis(self):
        # 获取音频文件列表
        supported_formats = ('.wav', '.mp3', '.ogg', '.flac', '.m4a', '.aac')
        audio_files = []
        for root, _, files in os.walk(self.input_dir):
            for file in files:
                if file.lower().endswith(supported_formats):
                    audio_files.append(os.path.join(root, file))

        if not audio_files:
            self.failed.emit("所选目录中没有找到支持的音频文件!")
            return

        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)

        success_count = 0
        error_messages = []
        total_files = len(audio_files)

        for i, audio_file in enumerate(audio_files):
            if self.cancelled:
                self.failed.emit("用户取消操作")
                return

            # 更新状态
            filename = os.path.basename(audio_file)
            self.status_update.emit(f"正在处理: {filename}")

            # 处理文件
            success, result = audio_analysis.plot_spectrogram_2d(audio_file, self.output_dir)
            if success:
                success_count += 1
            else:
                error_messages.append(result)

            # 更新进度
            progress = int((i + 1) / total_files * 100)
            self.progress.emit(progress)

        # 保存错误日志
        if error_messages:
            log_path = os.path.join(self.output_dir, "processing_errors.log")
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(error_messages))

        result_msg = f"处理完成!\n\n成功处理: {success_count} 个文件"
        if error_messages:
            result_msg += f"\n失败: {len(error_messages)} 个文件\n\n错误详情已保存到日志文件"

        self.finished_ok.emit(result_msg)

    def _run_3d_analysis(self):
        supported_formats = ('.wav', '.wave', '.aiff', '.flac')
        audio_files = []
        for root, _, files in os.walk(self.input_dir):
            for file in files:
                if file.lower().endswith(supported_formats):
                    audio_files.append(os.path.join(root, file))

        if not audio_files:
            self.failed.emit("未找到支持的音频文件")
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
            self.status_update.emit(f"正在生成3D频谱: {filename}")

            success, result = audio_analysis.plot_spectrogram_3d(audio_file, self.output_dir)
            if success:
                success_count += 1
            else:
                error_messages.append(result)

            progress = int((i + 1) / total_files * 100)
            self.progress.emit(progress)

        if error_messages:
            log_path = os.path.join(self.output_dir, "processing_errors.log")
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(error_messages))

        result_msg = f"处理完成!\n\n成功处理: {success_count} 个文件"
        if error_messages:
            result_msg += f"\n失败: {len(error_messages)} 个文件\n\n错误详情已保存到日志文件"

        self.finished_ok.emit(result_msg)

    def _run_centroid_analysis(self):
        audio_extensions = ['.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac']
        audio_files = []
        for root, _, files in os.walk(self.input_dir):
            for file in files:
                if os.path.splitext(file)[1].lower() in audio_extensions:
                    audio_files.append(os.path.join(root, file))

        if not audio_files:
            self.failed.emit("未找到任何支持的音频文件 (.wav, .mp3, .flac, .ogg, .m4a, .aac)")
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
            self.status_update.emit(f"正在分析频谱质心: {filename}")

            success, result = audio_analysis.analyze_audio_file_centroid(audio_file, self.output_dir)
            if success:
                success_count += 1
            else:
                error_messages.append(result)

            progress = int((i + 1) / total_files * 100)
            self.progress.emit(progress)

        if error_messages:
            log_path = os.path.join(self.output_dir, "processing_errors.log")
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(error_messages))

        result_msg = f"处理完成!\n\n成功处理: {success_count} 个文件"
        if error_messages:
            result_msg += f"\n失败: {len(error_messages)} 个文件\n\n错误详情已保存到日志文件"

        self.finished_ok.emit(result_msg)