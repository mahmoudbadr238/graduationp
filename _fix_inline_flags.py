"""Fix inline creationflags=0x08000000 and creationflags=subprocess.CREATE_NO_WINDOW."""
import re

files_and_fixes = {
    r'd:\graduationp\backend\engines\scanning\integrated_sandbox.py': [
        ('creationflags=0x08000000,  # CREATE_NO_WINDOW',
         'creationflags=0x08000000 if __import__("sys").platform == "win32" else 0,  # CREATE_NO_WINDOW'),
        ('creationflags=CREATE_NO_WINDOW',
         'creationflags=CREATE_NO_WINDOW if __import__("sys").platform == "win32" else 0'),
    ],
    r'd:\graduationp\backend\engines\sandbox_vmware\sandbox_controller.py': [
        ('creationflags=subprocess.CREATE_NO_WINDOW,',
         'creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,'),
    ],
    r'd:\graduationp\backend\engines\sandbox_vmware\preview_stream.py': [
        ('creationflags=0x08000000,   # CREATE_NO_WINDOW on Windows',
         'creationflags=0x08000000 if __import__("sys").platform == "win32" else 0,   # CREATE_NO_WINDOW on Windows'),
    ],
}

for filepath, replacements in files_and_fixes.items():
    try:
        with open(filepath, 'r', encoding='utf-8') as fh:
            txt = fh.read()
        changed = False
        for old, new in replacements:
            if old in txt:
                txt = txt.replace(old, new)
                changed = True
        if changed:
            # Ensure sys is imported in sandbox_controller
            if 'sandbox_controller' in filepath and 'import sys' not in txt:
                txt = txt.replace('import subprocess', 'import subprocess\nimport sys')
            with open(filepath, 'w', encoding='utf-8') as fh:
                fh.write(txt)
            print(f'Fixed: {filepath.split(chr(92))[-1]}')
        else:
            print(f'No changes needed: {filepath.split(chr(92))[-1]}')
    except FileNotFoundError:
        print(f'Not found: {filepath.split(chr(92))[-1]}')
    except Exception as e:
        print(f'Error in {filepath.split(chr(92))[-1]}: {e}')
