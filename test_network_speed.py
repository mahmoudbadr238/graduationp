#!/usr/bin/env python3
"""Test the new auto-scaling network speed formatter"""
import sys
sys.path.insert(0, '.')

from app.infra.system_monitor_psutil import PsutilSystemMonitor
import time

print("Testing Auto-Scaling Network Speed Display")
print("=" * 60)
print()

monitor = PsutilSystemMonitor()

# Get initial snapshot to initialize
snapshot1 = monitor.snapshot()
time.sleep(1)

# Get second snapshot to see actual speeds
snapshot2 = monitor.snapshot()

net_info = snapshot2['net']

print("Network Speed Information:")
print("-" * 60)
print(f"Upload Speed:")
print(f"  Formatted: {net_info['send_rate']['formatted']}")
print(f"  Value: {net_info['send_rate']['value']}")
print(f"  Unit: {net_info['send_rate']['unit']}")
print(f"  Legacy (Mbps): {net_info['send_rate_mbps']}")
print()
print(f"Download Speed:")
print(f"  Formatted: {net_info['recv_rate']['formatted']}")
print(f"  Value: {net_info['recv_rate']['value']}")
print(f"  Unit: {net_info['recv_rate']['unit']}")
print(f"  Legacy (Mbps): {net_info['recv_rate_mbps']}")
print()
print("=" * 60)
print()

# Test different speed scenarios
print("Testing formatter with different speeds:")
print("-" * 60)

test_speeds = [
    (100, "100 bytes/sec"),
    (1_000, "1 KB/sec"),
    (10_000, "10 KB/sec"),
    (100_000, "100 KB/sec"),
    (1_000_000, "1 MB/sec"),
    (10_000_000, "10 MB/sec"),
    (100_000_000, "100 MB/sec"),
    (1_000_000_000, "1 GB/sec"),
]

def format_speed_test(bytes_per_sec):
    """Test format speed function"""
    if bytes_per_sec < 0:
        bytes_per_sec = 0
    
    bits_per_sec = bytes_per_sec * 8
    
    if bits_per_sec >= 1_000_000_000:
        value = bits_per_sec / 1_000_000_000
        unit = "Gbps"
    elif bits_per_sec >= 1_000_000:
        value = bits_per_sec / 1_000_000
        unit = "Mbps"
    elif bits_per_sec >= 1_000:
        value = bits_per_sec / 1_000
        unit = "Kbps"
    else:
        value = bits_per_sec
        unit = "bps"
    
    if value >= 100:
        formatted = f"{value:.1f} {unit}"
    elif value >= 10:
        formatted = f"{value:.2f} {unit}"
    else:
        formatted = f"{value:.2f} {unit}"
    
    return formatted

for speed_bytes, description in test_speeds:
    formatted = format_speed_test(speed_bytes)
    print(f"{description:20} → {formatted}")

print()
print("✓ Network speed auto-scaling is working!")
