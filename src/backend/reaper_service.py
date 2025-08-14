import os
import subprocess
import psutil
from reapy import reascript_api as rpp

class ReaperService:
    """
    封装 Reaper 相关操作。
    """

    def is_reaper_running(self) -> bool:
        for p in psutil.process_iter(['name']):
            if p.info['name'] and p.info['name'].lower() == 'reaper.exe':
                return True
        return False

    def start_reaper(self, reaper_path: str):
        if not reaper_path or not os.path.exists(reaper_path):
            raise FileNotFoundError("未找到有效的 Reaper 启动文件路径")
        subprocess.Popen([reaper_path])

    def open_audio_in_reaper(self, audio_paths):
        for audio_path in audio_paths:
            rpp.InsertMedia(audio_path, 1)