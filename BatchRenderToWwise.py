import reapy
from waapi import WaapiClient
import os, sys, stat


def selected_audio_files():
    with WaapiClient() as client:
        # 获取选中的对象
        result = client.call("ak.wwise.ui.getSelectedObjects",
                             options={'return': ['originalFilePath', 'music:playlistRoot']})
        print("Wwise 返回的选中对象:", result)

        # 获取选中对象的路径
        selected_obj_paths = []
        if "objects" in result:
            for obj in result["objects"]:
                file_path = obj.get("originalFilePath", None)
                if file_path:
                    selected_obj_paths.append(file_path)
            print(file_path)
        return selected_obj_paths


num_items = reapy.reascript_api.CountSelectedMediaItems(0)

if num_items == 0:
    reapy.reascript_api.ShowConsoleMsg("没有选中任何音频！")

selected_audio_files = selected_audio_files()

for i in range(num_items):
    item = reapy.reascript_api.GetSelectedMediaItem(0, i)
    take = reapy.reascript_api.GetActiveTake(item)
    take_name = reapy.reascript_api.GetTakeName(take)
    # print(take_name)
    if take:
        for file_path in selected_audio_files:

            file_name_from_path = os.path.basename(file_path)
            print(file_name_from_path)
            if take_name == file_name_from_path:
                source_path = file_path

                if source_path:
                    # 设置渲染文件路径和渲染模式
                    source_path_parent_folder = os.path.dirname(source_path)
                    reapy.reascript_api.GetSetProjectInfo(0, "RENDER_SETTINGS", 32, True)
                    reapy.reascript_api.GetSetProjectInfo_String(0, "RENDER_FILE", source_path_parent_folder, True)

                    #reapy.reascript_api.GetSetProjectInfo_String(0, "RENDER_PATTERN", "", True)
                    reapy.reascript_api.GetSetProjectInfo_String(0, "RENDER_PATTERN", "$item", True)
                    reapy.reascript_api.Main_OnCommand(41824, 0)
                    reapy.reascript_api.ShowConsoleMsg(f"已覆盖渲染: {source_path}\n")
                    # 执行渲染命令

                else:
                    reapy.reascript_api.ShowConsoleMsg("无法获取源文件路径，跳过该 Item\n")

reapy.reascript_api.ShowMessageBox("所有选中的 Items 已覆盖渲染!", "完成", 0)

