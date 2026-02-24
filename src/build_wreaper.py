import argparse
import subprocess
import sys
from pathlib import Path


def build_args(src_dir: Path, console: bool = False) -> list[str]:
    data_sep = ";" if sys.platform.startswith("win") else ":"

    icon = src_dir / "favicon.ico"
    entry = src_dir / "WreaperRel.py"

    data_files = [
        "WwiseLogo.png",
        "reaperLogo.jpg",
        "test.jpg",
        "Open.png",
    ]

    hidden_imports = [
        "reapy",
        "numba",
        "audioread.ffdec",
        "reapy.reascript_api",
    ]

    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--onefile",
        "--name",
        "Wreaper",
        "--icon",
        str(icon),
    ]

    if not console:
        args.append("--noconsole")

    for file_name in data_files:
        file_path = src_dir / file_name
        args.extend(["--add-data", f"{file_path}{data_sep}."])

    for mod in hidden_imports:
        args.extend(["--hidden-import", mod])

    args.append(str(entry))
    return args


def validate_files(src_dir: Path) -> None:
    required = [
        src_dir / "favicon.ico",
        src_dir / "WwiseLogo.png",
        src_dir / "reaperLogo.jpg",
        src_dir / "test.jpg",
        src_dir / "Open.png",
        src_dir / "WreaperRel.py",
    ]

    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError("缺少以下构建文件:\n" + "\n".join(missing))


def main() -> int:
    parser = argparse.ArgumentParser(description="自动执行 Wreaper 的 PyInstaller 构建")
    parser.add_argument("--console", action="store_true", help="启用控制台窗口（默认关闭）")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    if (script_dir / "WreaperRel.py").exists():
        src_dir = script_dir
    else:
        src_dir = script_dir / "src"

    try:
        validate_files(src_dir)
    except FileNotFoundError as e:
        print(e)
        return 1

    cmd = build_args(src_dir=src_dir, console=args.console)
    print("开始构建 Wreaper...")
    print("工作目录:", src_dir)
    print("执行命令:", " ".join(f'\"{c}\"' if " " in c else c for c in cmd))

    result = subprocess.run(cmd, cwd=str(src_dir))
    if result.returncode == 0:
        print("构建完成。输出目录通常在 src/dist 和 src/build。")
    else:
        print(f"构建失败，退出码: {result.returncode}")

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
