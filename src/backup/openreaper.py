import psutil
import subprocess
import sys
import os
import tkinter as tk
from tkinter import filedialog
import time

CONFIG_FILE = 'config.txt'

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
    try:
        if os.path.exists(reaper_path):
            subprocess.Popen([reaper_path])  # 启动 Reaper
            print(f"Reaper 已启动: {reaper_path}")
        else:
            print(f"Reaper 路径无效: {reaper_path}")
    except Exception as e:
        print(f"启动 Reaper 时发生错误: {e}")




def main():
    reaper_path = get_default_reaper_path()

    if reaper_path is None:
        print("未找到默认路径，您需要手动选择 Reaper 启动文件.")
        reaper_path = select_new_reaper_project()
        if reaper_path:
            save_reaper_path(reaper_path)
    start_reaper(reaper_path)

if __name__ == "__main__":
    main()
