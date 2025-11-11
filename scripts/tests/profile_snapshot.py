#!/usr/bin/env python
"""Profile performance hotspots in the app."""

import time

from app.infra.system_monitor_psutil import PsutilSystemMonitor

m = PsutilSystemMonitor()

# Time snapshot operations
iterations = 5
print("Profiling snapshot performance...")

for i in range(iterations):
    start = time.perf_counter()
    s = m.snapshot()
    elapsed = (time.perf_counter() - start) * 1000

    print(f"\nIteration {i + 1}: {elapsed:.1f}ms")

    # Break down by component
    start = time.perf_counter()
    m._get_cpu_info()
    cpu_time = (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    m._get_memory_info()
    mem_time = (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    m._get_gpu_info_cached()  # Use cached method
    gpu_time = (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    m._get_network_info()
    net_time = (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    m._get_disk_info()
    disk_time = (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    m._get_security_info_cached()
    sec_time = (time.perf_counter() - start) * 1000

    print(f"  CPU: {cpu_time:.1f}ms | Mem: {mem_time:.1f}ms | GPU: {gpu_time:.1f}ms")
    print(f"  Net: {net_time:.1f}ms | Disk: {disk_time:.1f}ms | Sec: {sec_time:.1f}ms")
    print(f"  GPU is {(gpu_time / elapsed) * 100:.0f}% of total")
