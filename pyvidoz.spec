# -*- mode: python ; coding: utf-8 -*-
# Build with: pyinstaller pyvidoz.spec  (or scripts/build_exe.py, which also
# copies ffmpeg.exe/ffprobe.exe into dist/PyVidoz/ afterwards).
#
# Onedir build with contents_directory="." so bundled files (fonts, Qt
# plugins, etc.) land directly next to PyVidoz.exe instead of in a separate
# _internal/ folder -- config.BASE_DIR and theme.FONTS_DIR both resolve
# relative to sys.executable's parent, so this keeps that assumption true.

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/fonts', 'assets/fonts')],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='PyVidoz',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon='assets/icon.ico',
    version='version_info.txt',
    contents_directory='.',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PyVidoz',
)
