import subprocess
import sys
import time


def restart_application():
    """启动应用并等待应用退出"""
    # 获取当前脚本路径
    script_path = sys.argv[0]

    # 启动当前应用程序
    process = subprocess.Popen([sys.executable, 'wreaper.py'])

    # 等待应用退出
    process.wait()


if __name__ == "__main__":
    restart_application()
