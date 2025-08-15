import os
import sys

def replace_and_restart():
    """
    使用临时批处理在 Windows 下替换 wreaper.exe，并重启新版本。
    """
    bat_content = (
        "@echo off\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        "taskkill /f /im Wreaper.exe >nul 2>&1\r\n"
        "if exist Wreaper_new.exe (\r\n"
        "  del /f /q Wreaper.exe >nul 2>&1\r\n"
        "  ren Wreaper_new.exe Wreaper.exe\r\n"
        "  start \"\" Wreaper.exe\r\n"
        ") else (\r\n"
        "  echo 未找到新文件\r\n"
        "  pause\r\n"
        ")\r\n"
    )
    with open("update.bat", "w", encoding="utf-8") as f:
        f.write(bat_content)
    os.startfile("update.bat")
    sys.exit()