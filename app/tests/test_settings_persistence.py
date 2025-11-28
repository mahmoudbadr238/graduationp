#!/usr/bin/env python3
"""Test script to verify Settings persistence"""

import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.ui.settings_service import SettingsService

def test_settings_persistence():
    """Test that settings save and load correctly"""
    
    # Create settings service
    settings = SettingsService()
    
    print("[Test] Initial settings:")
    print(f"  - Theme Mode: {settings.themeMode}")
    print(f"  - Font Size: {settings.fontSize}")
    
    # Change font size
    print("\n[Test] Changing font size to 'large'...")
    settings.fontSize = "large"
    
    # Verify it was set
    print(f"  - Font Size after set: {settings.fontSize}")
    
    # Create new instance (simulates app restart/new page load)
    print("\n[Test] Creating new SettingsService instance (simulating app reload)...")
    settings2 = SettingsService()
    print(f"  - Font Size from new instance: {settings2.fontSize}")
    
    # Verify persistence
    if settings2.fontSize == "large":
        print("\n✅ SUCCESS: Settings persisted correctly!")
        return True
    else:
        print(f"\n❌ FAILURE: Expected 'large', got '{settings2.fontSize}'")
        return False

if __name__ == "__main__":
    success = test_settings_persistence()
    sys.exit(0 if success else 1)
