# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['_exe_entry.py'],
    pathex=[],
    binaries=[],
    datas=[('drs_version_audit.py', '.'), ('drs_audit_gui.py', '.'), ('crm_client.py', '.')],
    hiddenimports=['drs_version_audit', 'drs_audit_gui', 'crm_client'],
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
    name='DRS Version Audit',
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
)
