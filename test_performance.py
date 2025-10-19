#!/usr/bin/env python3
"""Test individual component performance"""
import sys
import time
sys.path.insert(0, '.')

from app.infra.system_monitor_psutil import PsutilSystemMonitor

m = PsutilSystemMonitor()

components = [
    ('CPU', m._get_cpu_info),
    ('Memory', m._get_memory_info),
    ('GPU', m._get_gpu_info),
    ('Network', m._get_network_info),
    ('Disk', m._get_disk_info),
    ('OS', m._get_os_info),
    ('Security', m._get_security_info),
]

print("Performance Profile:")
print("-" * 40)

total_time = 0
for name, func in components:
    start = time.time()
    result = func()
    elapsed = (time.time() - start) * 1000
    total_time += elapsed
    
    status = "✓" if elapsed < 100 else "⚠" if elapsed < 500 else "✗"
    print(f"{status} {name:12} {elapsed:6.0f}ms")

print("-" * 40)
print(f"  Total:       {total_time:6.0f}ms")
print()

# Test full snapshot
start = time.time()
snapshot = m.snapshot()
snapshot_time = (time.time() - start) * 1000
print(f"Full Snapshot:  {snapshot_time:6.0f}ms")
print()

if snapshot_time < 200:
    print("✓ Performance is EXCELLENT (< 200ms)")
elif snapshot_time < 1000:
    print("⚠ Performance is ACCEPTABLE (< 1000ms)")
else:
    print("✗ Performance is TOO SLOW (> 1000ms)")
