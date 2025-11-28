#!/usr/bin/env python3
"""Test theme persistence end-to-end"""

import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.ui.settings_service import SettingsService

def test_theme_persistence():
    """Test that theme mode saves and loads correctly"""
    
    print("=" * 60)
    print("TEST 1: Initial state")
    print("=" * 60)
    
    # Create settings service
    settings = SettingsService()
    print(f"Initial Theme Mode: {settings.themeMode}")
    print(f"Settings file: {settings._settings_path}")
    
    # Check what's on disk
    if settings._settings_path.exists():
        with open(settings._settings_path, 'r') as f:
            disk_data = json.load(f)
            print(f"On disk (themeMode): {disk_data.get('themeMode', 'NOT FOUND')}")
    
    print("\n" + "=" * 60)
    print("TEST 2: Change theme to 'dark'")
    print("=" * 60)
    
    settings.themeMode = "dark"
    print(f"After set to 'dark': {settings.themeMode}")
    
    # Check what's on disk
    if settings._settings_path.exists():
        with open(settings._settings_path, 'r') as f:
            disk_data = json.load(f)
            print(f"On disk (themeMode): {disk_data.get('themeMode', 'NOT FOUND')}")
    
    print("\n" + "=" * 60)
    print("TEST 3: Create NEW instance (simulates app reload)")
    print("=" * 60)
    
    # Create new instance
    settings2 = SettingsService()
    print(f"New instance theme: {settings2.themeMode}")
    
    if settings2.themeMode == "dark":
        print("✅ SUCCESS: Theme persisted correctly!")
        return True
    else:
        print(f"❌ FAILURE: Expected 'dark', got '{settings2.themeMode}'")
        return False

if __name__ == "__main__":
    success = test_theme_persistence()
    sys.exit(0 if success else 1)
