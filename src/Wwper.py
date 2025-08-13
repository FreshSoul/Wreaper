from waapi import WaapiClient
import reapy
import psutil
import subprocess
import stat
import os
import tkinter as tk
from tkinter import filedialog

CONFIG_FILE = 'reaperconfig.txt'

def get_default_reaper_path():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as file:
            path = file.read().strip()
            if os.path.exists(path):
                return path
    return None

def save_reaper_path(path):
    with open(CONFIG_FILE, 'w') as file:
        file.write(path)

def select_new_reaper_project():
    root = tk.Tk()
    root.withdraw()
    file_selected = filedialog.askopenfilename(
        title="选择 REAPER 启动文件",
        filetypes=[("Executable files", "*.exe")]
    )
    return file_selected



def start_reaper(reaper_path):
    if os.path.exists(reaper_path):
        subprocess.Popen([reaper_path])
        print(f"Reaper 已启动: {reaper_path}")
    else:
        print(f"Reaper 路径无效: {reaper_path}")

def is_reaper_running():
    for proc in psutil.process_iter(attrs=['pid', 'name']):
        if 'reaper.exe' in proc.info['name'].lower():
            return True
    return False


def get_selected_audio_files():
    with WaapiClient() as client:
        # 获取选中的对象
        result = client.call("ak.wwise.ui.getSelectedObjects",options = {'return':['originalFilePath','music:playlistRoot']} )
        print("Wwise 返回的选中对象:", result)

        # 获取选中对象的路径
        selected_obj_paths = []
        if "objects" in result:
            for obj in result["objects"]:
                file_path = obj.get("originalFilePath", None)
                if file_path:
                    selected_obj_paths.append(file_path)
        return selected_obj_paths


def open_audio_in_reaper(audio_paths):
      if audio_paths:
          for audio_path in audio_paths:
            reapy.reascript_api.InsertMedia(audio_path, 1)
            print(f"已在 Reaper 中打开音频文件: {audio_path}")
      else:
          print("未能获取到音频文件路径.")

def remove_readonly_attribute(file_path):
    if os.path.exists(file_path):
       os.chmod(file_path, stat.S_IWRITE)

def main():
    reaper_path = get_default_reaper_path()
    if reaper_path is None:
        print("未找到默认路径，您需要手动选择 Reaper 启动文件.")
        reaper_path = select_new_reaper_project()
        if reaper_path:
            save_reaper_path(reaper_path)

    if is_reaper_running():
        print("Reaper 已经在运行.")
    else:
        print("Reaper 没有启动，正在启动 Reaper...")
        start_reaper(reaper_path)


    selected_audio_files = get_selected_audio_files()
    if selected_audio_files:
        for file_path in selected_audio_files:
            remove_readonly_attribute(file_path)
        open_audio_in_reaper(selected_audio_files)
    else:
        print("没有选中的音频文件.")

if __name__ == "__main__":
    main()