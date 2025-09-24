import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from reapy import reascript_api as rpp
import json
from backend.wwise_service import WwiseService
from backend.reaper_service import ReaperService
import stat

REGION_INDEX_MAP = {}

def remove_readonly_attribute(file_path):
    if os.path.exists(file_path):
        os.chmod(file_path, stat.S_IWRITE)

def import_wwise_files_and_create_regions():
    # 获取 Wwise 选中的音频文件路径
    wwise_service = WwiseService()
    selected_audio_files = wwise_service.get_selected_audio_files()
    print(f"Wwise 选中的音频文件: {selected_audio_files}")
    if selected_audio_files:
        for file_path in selected_audio_files:
            remove_readonly_attribute(file_path)
        try:
            # 导入音频到 Reaper
            reaper_service = ReaperService()
            reaper_service.open_audio_in_reaper(selected_audio_files)
            # 为每个导入的音频插入同名区间
            num_items = rpp.CountSelectedMediaItems(0)
            last_end = None
            for i in range(num_items):
                item = rpp.GetSelectedMediaItem(0, i)
                length = rpp.GetMediaItemInfo_Value(item, "D_LENGTH")
                if last_end is None:
                    start = rpp.GetMediaItemInfo_Value(item, "D_POSITION")
                else:
                    start = last_end + 1.0  # 上一个区间结束后1秒
                    rpp.SetMediaItemInfo_Value(item, "D_POSITION", start)
                end = start + length
                last_end = end
                region_name = os.path.splitext(os.path.basename(selected_audio_files[i]))[0]
                idx = rpp.AddProjectMarker2(0, True, start, end, region_name, -1, 0)
                REGION_INDEX_MAP[idx] = selected_audio_files[i]
            print("导入并创建区间完成。")
            
        except Exception as e:
            print(f"导入音频到Reaper时出错: {e}")
        print(f"REGION_INDEX_MAP: {REGION_INDEX_MAP}")
    else:
        print("没有选中的音频文件。")

def render_selected_regions_to_original_paths():
    """
    只渲染选中的区间，将内容覆盖回区间index对应的原始文件路径。
    """
    retval, num_markers, num_regions, num_total = rpp.CountProjectMarkers(0, 0, 0)
    print(num_total)
    rendered = []
    unmatched = []
    print(f"REGION_INDEX_MAP: {REGION_INDEX_MAP}")
    for i in range(num_total):
        retval, proj, idx, isrgnOut, posOut, rgnendOut, nameOut, markrgnindexnumberOut = rpp.EnumProjectMarkers2(0, i, 0, 0.0, 0.0, '', 0)
        print(retval, proj, idx, isrgnOut, posOut, rgnendOut, nameOut, markrgnindexnumberOut)
        if isrgnOut and idx < 0:
            region_idx = markrgnindexnumberOut
            print("region_idx:{region_idx}")
            if region_idx in REGION_INDEX_MAP:
                out_path = REGION_INDEX_MAP[region_idx]
                out_dir = os.path.dirname(out_path)
                if not os.access(out_dir, os.W_OK):
                    print(f"目录不可写: {out_dir}")
                    continue
                # 设置渲染区间
                rpp.GetSet_LoopTimeRange(True, False, posOut, rgnendOut, False)
                rpp.GetSetProjectInfo(0, "RENDER_SETTINGS", 0, True) 
                rpp.GetSetProjectInfo(0, "RENDER_TAILFLAG", 32, True)
                rpp.GetSetProjectInfo_String(0, "RENDER_FILE", out_dir, True)
                rpp.GetSetProjectInfo_String(0, "RENDER_PATTERN", os.path.basename(out_path), True)
                rpp.Main_OnCommand(41824, 0)  # 渲染
                rendered.append(out_path)
            else:
                unmatched.append(region_idx)

    print("已渲染的文件：", rendered)
    if unmatched:
        print("未匹配到原路径的区间索引：", unmatched)








# 需要时调用
if __name__ == "__main__":
    import_wwise_files_and_create_regions()
    #render_selected_regions_to_original_paths() 
    