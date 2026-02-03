#!/usr/bin/env python
"""Test AMD GPU collection"""
import sys
sys.path.insert(0, '.')

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from app.gpu.telemetry_worker import (
    collect_amd_wmi_metrics, 
    collect_amd_adl_metrics, 
    collect_amd_metrics
)

def run_with_timeout(func, timeout, default):
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func)
            return future.result(timeout=timeout)
    except (FuturesTimeoutError, Exception) as e:
        import traceback
        print(f'TIMEOUT/ERROR: {type(e).__name__}: {e}')
        traceback.print_exc()
        return default

print("Testing WMI collection DIRECTLY:")
wmi_gpus = collect_amd_wmi_metrics()
print(f"  WMI returned {len(wmi_gpus)} GPUs")
for g in wmi_gpus:
    name = g['name']
    usage = g['usage']
    mem_used = g['memUsedMB']
    mem_total = g['memTotalMB']
    driver = g['driverVersion']
    print(f"    {name}: usage={usage}%, mem={mem_used}/{mem_total}MB, driver={driver}")

print("\nTesting WMI collection WITH TIMEOUT WRAPPER:")
wmi_gpus2 = run_with_timeout(collect_amd_wmi_metrics, 10.0, [])
print(f"  WMI with timeout returned {len(wmi_gpus2)} GPUs")
for g in wmi_gpus2:
    print(f"    {g['name']}: usage={g['usage']}%")

print("\nTesting combined with timeout:")
combined = run_with_timeout(lambda: collect_amd_metrics(True, True), 10.0, [])
print(f"  Combined returned {len(combined)} GPUs")
for g in combined:
    source = g.get('source', 'N/A')
    print(f"    {g['name']}: source={source}, usage={g['usage']}%")

