# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# Determine project root directory (parent of installer/)
SPEC_DIR = os.path.dirname(os.path.abspath(SPEC)) if 'SPEC' in locals() else os.path.abspath('.')
if os.path.basename(SPEC_DIR) == 'installer':
    ROOT_DIR = os.path.dirname(SPEC_DIR)
else:
    ROOT_DIR = SPEC_DIR

# Add ROOT_DIR to sys.path so modules can be imported
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

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
    (os.path.join(ROOT_DIR, 'src'), 'src'),
    (os.path.join(ROOT_DIR, 'guides'), 'guides'),
    (os.path.join(ROOT_DIR, 'assets'), 'assets'),
]

# Include version file
version_file = os.path.join(ROOT_DIR, '.version')
if os.path.exists(version_file):
    datas.append((version_file, '.'))

# Optional certifi bundle
try:
    import certifi
    datas.append((certifi.where(), 'certifi'))
except ImportError:
    pass

icon_path = os.path.join(ROOT_DIR, 'assets', 'icon.ico')
icon_file = icon_path if os.path.exists(icon_path) else None

a = Analysis(
    [os.path.join(ROOT_DIR, 'run_ui.py')],
    pathex=[ROOT_DIR],
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
    icon=icon_file,
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
