# PHASE 1 CLEANUP - CHANGELOG

## Date: October 26, 2025

### Files Removed (34 total)

#### Test Files (21 files)
- test_amd_fix.py
- test_amd_full.py
- test_amd_lib.py
- test_amd_usage.py
- test_amd_vram.py
- test_backend.py
- test_backend_live.py
- test_backend_simple.py
- test_detection.py
- test_gpu_consistency.py
- test_gpu_mapping.py
- test_gpu_order.py
- test_gpu_perf.py
- test_gpu_service.py
- test_network_speed.py
- test_performance.py
- test_phys_order.py
- test_pnp_mapping.py
- test_pyadl.py
- test_pyadl_methods.py
- test_thermal.py

#### Backup Files (2 files)
- app/infra/system_monitor_psutil.py.bak
- qml/pages/snapshot/HardwarePage_temp.qml

#### Legacy/Duplicate Files (1 file)
- qml/pages/GPUMonitoring.qml (replaced by GPUMonitoringNew.qml)

#### Dev Utility Files (7 files)
- check_gpu_method.py
- fix_escapes.py
- fix_unicode.py
- optimize_further.py
- optimize_performance.py
- replace_gpu_method.py
- update_app.py

### Files Modified

#### qml/components/qmldir
- Removed singleton Theme reference (now uses ../theme/Theme)
- Added TopBar component

#### qml/pages/qmldir
- Removed GPUMonitoring.qml reference
- Kept only GPUMonitoringNew.qml

### Files Created

#### scripts/purge_unused.ps1
- Cleanup script for removing unused files
- Can be re-run safely

### Known Issues to Fix

1. **Theme Import Error**: Components trying to import Theme locally
   - Need to update all components to `import "../theme"` 
   - Affects: AppSurface, Panel, SidebarNav, SectionHeader, and more

2. **StackView Anchor Conflicts**: Minor warning in GPUMonitoringNew.qml

### Next Steps

1. Update all component QML files to import Theme from "../theme"
2. Test application startup
3. Add code quality tooling (ruff, mypy, qmllint)
4. Create graceful fallbacks for missing tools
