# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('playwright')

a = Analysis(
    ['desktop/main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas + [('assets', 'assets'), ('data', 'data')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='Hn38videoAItool',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    console=False, icon='assets/hn38.ico',
)
coll = COLLECT(
    exe, a.binaries, a.datas, strip=False, upx=True, name='Hn38videoAItool',
)
