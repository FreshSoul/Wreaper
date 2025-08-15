# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['WreaperRel.py'],
    pathex=[],
    binaries=[],
    datas=[('WwiseLogo.png', '.'), ('reaperLogo.jpg', '.'), ('test.jpg', '.')],
    hiddenimports=['reapy', 'librosa', 'numba', 'audioread.ffdec', 'reapy.reascript_api'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Wreaper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['favicon.ico'],
)
