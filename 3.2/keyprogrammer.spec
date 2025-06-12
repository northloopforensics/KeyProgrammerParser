# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['KeyProgrammerParser.py'],
    pathex=[],
    binaries=[],
    datas=[('report_template.html', '.')],  # Include the template file
    hiddenimports=[
        'vininfo', 
        'pyvin', 
        'jinja2.ext',
        'pandas',
        'sqlite3',
        'customtkinter'
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

pyz = PYZ(
    a.pure, 
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='KeyProgrammerParser',
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
    icon='./digital-key-2.ico',  # Add an icon file if you have one
)