import os
import sys

def resource_path(relative_path: str) -> str:
    """
    获取资源文件绝对路径，兼容 PyInstaller 打包 (_MEIPASS).
    """
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    # utils/ 相对到项目 src 根目录
    src_root = os.path.dirname(base_path) if os.path.basename(base_path).lower() == "utils" else base_path
    return os.path.join(src_root, relative_path)