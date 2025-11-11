#!/usr/bin/env python
"""Test disk calculation matches what UI should show."""

from app.infra.system_monitor_psutil import PsutilSystemMonitor

m = PsutilSystemMonitor()
s = m.snapshot()

disks = s.get("disks", [])
print(f"Found {len(disks)} disks:")

total_used = 0
total_capacity = 0

for d in disks:
    print(
        f"  {d['device']}: {d['percent']:.1f}% ({d['used'] / (1024**3):.0f} GB / {d['total'] / (1024**3):.0f} GB)"
    )
    total_used += d["used"]
    total_capacity += d["total"]

if total_capacity > 0:
    avg_pct = (total_used / total_capacity) * 100
    print(f"\nAverage across all drives: {avg_pct:.1f}%")
    print(
        f"Total: {total_used / (1024**3):.0f} GB / {total_capacity / (1024**3):.0f} GB ({len(disks)} drives)"
    )
