#!/usr/bin/env python
"""Test AMD WMI collection"""
import sys
sys.path.insert(0, 'D:/graduationp')

from app.gpu.telemetry_worker import (
    init_nvidia, init_amd_adl, init_amd_wmi,
    collect_nvidia_metrics, collect_amd_metrics
)

# Init
print("=== Initializing vendors ===")
nvml = init_nvidia()
adl = init_amd_adl()
wmi = init_amd_wmi()
print(f'  nvml={nvml}, adl={adl}, wmi={wmi}')

# Collect all
print()
print("=== Collecting all GPUs ===")
all_gpus = []
all_gpus.extend(collect_nvidia_metrics(nvml))
all_gpus.extend(collect_amd_metrics(adl, wmi))

# Re-assign IDs like the worker does
for idx, gpu in enumerate(all_gpus):
    gpu['id'] = idx

print(f'Total GPUs: {len(all_gpus)}')
print()
print("=== GPU list as sent to QML (indices match GPUService.metrics) ===")
for g in all_gpus:
    idx = g['id']
    name = g['name']
    vendor = g['vendor']
    usage = g['usage']
    mem_used = g['memUsedMB']
    mem_total = g['memTotalMB']
    driver = g['driverVersion']
    print(f"Index {idx}: {name} ({vendor})")
    print(f"  usage={usage}, mem={mem_used}/{mem_total}MB, driver={driver}")
