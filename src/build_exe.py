import os
import PyInstaller


def build():
    # 添加资源文件
    add_data = [
        ('WwiseLogo.png', '.'),
        ('reaperLogo.jpg', '.'),
        ('test.jpg', '.')
    ]

    # 转换为PyInstaller格式
    data_args = []
    for src, dst in add_data:
        data_args.append('--add-data')
        data_args.append(f'{os.path.abspath(src)};{dst}')

    # PyInstaller参数
    pyinstaller_args = [
                           'wreaper.py',
                           '--name=Wreaper',
                           '--onefile',
                           '--windowed',  # 不显示控制台窗口
                           '--icon=favicon.ico',  # 可选图标
                           '--noconfirm',
                           '--clean'
                       ] + data_args

    # 运行PyInstaller
    PyInstaller.__main__.run(pyinstaller_args)


if __name__ == '__main__':
    build()