#!/usr/bin/env python
"""Test snapshot performance after GPU removal."""

import time

from app.infra.system_monitor_psutil import PsutilSystemMonitor

m = PsutilSystemMonitor()

print("Testing snapshot performance (GPU disabled)...")
for i in range(3):
    start = time.perf_counter()
    s = m.snapshot()
    elapsed = (time.perf_counter() - start) * 1000
    print(f"Iteration {i + 1}: {elapsed:.1f}ms | Disks: {len(s['disks'])}")
