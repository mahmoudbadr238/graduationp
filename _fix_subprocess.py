"""Fix _SUBPROCESS_FLAGS across all backend files for cross-platform support."""
import os

files = [
    r'd:\graduationp\backend\utils\security_snapshot.py',
    r'd:\graduationp\backend\utils\security_info.py',
    r'd:\graduationp\backend\infra\system_monitor_psutil.py',
    r'd:\graduationp\backend\infra\nmap_cli.py',
    r'd:\graduationp\backend\engines\scanning\static_scan.py',
    r'd:\graduationp\backend\engines\scanning\clamav_adapter.py',
    r'd:\graduationp\backend\engines\sandbox_vmware\vmrun_client.py',
    r'd:\graduationp\backend\engines\sandbox\engines.py',
    r'd:\graduationp\backend\engines\sandbox\analyzer_static.py',
    r'd:\graduationp\backend\engines\ai\security_chatbot_v4.py',
    r'd:\graduationp\backend\api\system_snapshot_service.py',
]

old = '_SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW'
new = '_SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0'

for f in files:
    with open(f, 'r', encoding='utf-8') as fh:
        txt = fh.read()
    if old in txt:
        # Also ensure sys is imported
        if 'import sys' not in txt and 'sys.platform' not in txt:
            # Add sys import after subprocess import
            txt = txt.replace('import subprocess', 'import subprocess\nimport sys')
        txt = txt.replace(old, new)
        with open(f, 'w', encoding='utf-8') as fh:
            fh.write(txt)
        print(f'Fixed: {os.path.basename(f)}')
    else:
        print(f'Already fixed: {os.path.basename(f)}')
