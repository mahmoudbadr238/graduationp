#!/usr/bin/env python3
"""Sentinel - Endpoint Security Suite v1.0.0"""
import sys
import os
from app.utils.admin import AdminPrivileges
from app.application import run
from app.__version__ import __version__, APP_FULL_NAME

if __name__ == "__main__":
    print(f"{APP_FULL_NAME} v{__version__}")
    
    # Check for admin privileges and auto-elevate if needed
    # This ensures full access to Security event logs
    if not AdminPrivileges.is_admin():
        print("[WARNING] Administrator privileges required for full functionality")
        print("  Requesting UAC elevation...")

        # elevate() will prompt for admin, restart the app, and exit this process
        AdminPrivileges.elevate()

        # If we're still here, user declined or it failed
        print("[WARNING] Elevation declined or failed. Continuing with limited access...")
        print("  Some features (Security event logs) may be unavailable.\n")
    else:
        print("[OK] Running with administrator privileges\n")

    raise SystemExit(run())