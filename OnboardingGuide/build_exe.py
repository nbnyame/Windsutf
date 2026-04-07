"""
Build script for creating the Winmark Onboarding Guide executable.
Run:  python build_exe.py
"""
import PyInstaller.__main__
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PyInstaller.__main__.run([
    os.path.join(BASE_DIR, 'launcher.py'),
    '--name=WinmarkOnboardingGuide',
    '--onefile',
    '--noconsole',
    '--icon', os.path.join(BASE_DIR, 'winmark.ico'),
    # Bundle the templates folder and faq_data module
    '--add-data', f'{os.path.join(BASE_DIR, "backend", "templates")};backend/templates',
    '--add-data', f'{os.path.join(BASE_DIR, "backend", "faq_data.py")};backend',
    '--add-data', f'{os.path.join(BASE_DIR, "backend", "employee_lookup.py")};backend',
    # Tell PyInstaller where to find faq_data
    '--paths', os.path.join(BASE_DIR, 'backend'),
    '--hidden-import', 'faq_data',
    '--hidden-import', 'employee_lookup',
    '--hidden-import', 'flask',
    '--hidden-import', 'flask_cors',
    '--hidden-import', 'jinja2.ext',
    '--distpath', os.path.join(BASE_DIR, 'dist'),
    '--workpath', os.path.join(BASE_DIR, 'build'),
    '--specpath', BASE_DIR,
    '--clean',
    '-y',
])
