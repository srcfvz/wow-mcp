# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Collect customtkinter data files (theme files, etc.)
ctk_datas = collect_data_files('customtkinter')

# We assume this spec file is in wow-mcp/desktop-app/
repo_root = os.path.abspath(os.path.join(os.getcwd(), '..'))
mcp_server_path = os.path.join(repo_root, 'mcp-server')
desktop_app_path = os.path.abspath(os.getcwd())

a = Analysis(
    ['main.py'],
    pathex=[desktop_app_path, mcp_server_path],
    binaries=[],
    datas=ctk_datas,
    hiddenimports=[
        'pystray', 
        'PIL', 
        'keyring', 
        'keyring.backends.Windows',
        'win32timezone'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='WowMCP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # Set to False for GUI app (no terminal window)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='icon.ico', # TODO: Add icon later
)
