#!/usr/bin/env python
"""Quick test to verify disk detection in snapshot."""
from app.infra.system_monitor_psutil import PsutilSystemMonitor

m = PsutilSystemMonitor()
s = m.snapshot()

disks = s.get('disks', [])
print(f'Disks count: {len(disks)}')
for d in disks:
    print(f'{d["device"]} -> {d["mountpoint"]} | {d["percent"]}% | {d["used"]/(1024**3):.1f}GB / {d["total"]/(1024**3):.1f}GB')
