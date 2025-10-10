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
    
    def open_audioRegion_in_reaper(self, audio_paths):
        last_end = None
        for audio_path in audio_paths:
            # 插入音频
            rpp.InsertMedia(audio_path, 1)
            # 获取最后一个插入的 item
            num_items = rpp.CountMediaItems(0)
            item = rpp.GetMediaItem(0, num_items - 1)
            length = rpp.GetMediaItemInfo_Value(item, "D_LENGTH")
            if last_end is None:
                start = rpp.GetMediaItemInfo_Value(item, "D_POSITION")
            else:
                start = last_end + 1.0  # 上一个区间结束后1秒
                rpp.SetMediaItemInfo_Value(item, "D_POSITION", start)
            end = start + length
            last_end = end
            region_name = os.path.splitext(os.path.basename(audio_path))[0]
            rpp.AddProjectMarker2(0, True, start, end, region_name, -1, 0)
                