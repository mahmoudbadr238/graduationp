# app/core/perf_monitor.py
"""
Lightweight in-app performance monitor for Sentinel.

Logs CPU and memory usage for the Sentinel process periodically.
Runs in a daemon thread, integrates with existing logging system.

Example log output:
    [PERF] CPU=  5.3%  MEM= 420.7 MB
    [PERF] CPU= 78.4%  MEM= 980.2 MB
"""

import logging
import os
import threading
import time

import psutil

log = logging.getLogger("perf")


def start_perf_monitor(interval_seconds: int = 5) -> None:
    """
    Periodically log CPU and memory usage for the Sentinel process.

    - Runs in a daemon thread (no blocking of UI).
    - Uses the existing logging system so entries go to sentinel.log.
    - Safe to call once at startup.
    - Starts after a delay to avoid impacting startup performance.

    Args:
        interval_seconds: Time between measurements (default: 5 seconds).
    """
    proc = psutil.Process(os.getpid())

    def _loop() -> None:
        # Wait 5 seconds before starting to let app stabilize
        time.sleep(5)
        
        # First call primes cpu_percent, subsequent calls measure since last call
        _ = proc.cpu_percent(interval=None)
        while True:
            try:
                cpu = proc.cpu_percent(interval=None)  # % over last measurement window
                mem_mb = proc.memory_info().rss / (1024 * 1024)
                log.info(f"[PERF] CPU={cpu:5.1f}%  MEM={mem_mb:7.1f} MB")
            except Exception as e:
                log.warning(f"[PERF] monitor error: {e}")
            time.sleep(interval_seconds)

    t = threading.Thread(target=_loop, daemon=True, name="perf-monitor")
    t.start()
    log.info(f"[PERF] Performance monitor started (interval={interval_seconds}s)")
