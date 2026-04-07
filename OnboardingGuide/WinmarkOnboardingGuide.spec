# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\nnyamekye\\CascadeProjects\\windsurf-project\\OnboardingGuide\\launcher.py'],
    pathex=['C:\\Users\\nnyamekye\\CascadeProjects\\windsurf-project\\OnboardingGuide\\backend'],
    binaries=[],
    datas=[('C:\\Users\\nnyamekye\\CascadeProjects\\windsurf-project\\OnboardingGuide\\backend\\templates', 'backend/templates'), ('C:\\Users\\nnyamekye\\CascadeProjects\\windsurf-project\\OnboardingGuide\\backend\\faq_data.py', 'backend'), ('C:\\Users\\nnyamekye\\CascadeProjects\\windsurf-project\\OnboardingGuide\\backend\\employee_lookup.py', 'backend')],
    hiddenimports=['faq_data', 'employee_lookup', 'flask', 'flask_cors', 'jinja2.ext'],
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
    name='WinmarkOnboardingGuide',
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
    icon=['C:\\Users\\nnyamekye\\CascadeProjects\\windsurf-project\\OnboardingGuide\\winmark.ico'],
)
