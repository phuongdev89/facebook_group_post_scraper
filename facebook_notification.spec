# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# Collect all modules from src
src_submodules = collect_submodules('src')
requests_submodules = collect_submodules('requests')

hidden_imports = [
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'sqlite3',
    'requests',
    'urllib3',
    'certifi',
    'charset_normalizer',
] + src_submodules + requests_submodules

datas = [
    ('src', 'src'),
    ('guides', 'guides'),
]

# Include version file
if os.path.exists('.version'):
    datas.append(('.version', '.'))

# Optional certifi bundle
try:
    import certifi
    datas.append((certifi.where(), 'certifi'))
except ImportError:
    pass

a = Analysis(
    ['run_ui.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'torch', 'torchaudio', 'transformers', 'notebook'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

# Standalone directory distribution
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FacebookNotification',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # Windowed GUI application (no black console window)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='FacebookNotification',
)
