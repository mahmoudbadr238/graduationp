# CHANGELOG - QML UI Refactor

## [2024-10-17] - Complete QML Architecture Refactor

### ✨ Major Improvements

**Theme System**
- Implemented singleton Theme pattern via `qmldir` module system
- Centralized all design tokens (colors, spacing, radii, typography, motion)
- Fixed property naming: removed nested objects, now using direct properties (`Theme.text`, `Theme.spacing_md`, `Theme.radii_lg`)
- Typography now uses JavaScript object pattern for h1, h2, body, mono styles

**Component Architecture**
- Fixed all component imports to use module imports (`import "../components"`) instead of direct file paths
- Removed circular/incorrect import dependencies
- Fixed QtQuick.Effects import syntax (removed version numbers for Qt 6.9 compatibility)
- Updated all components to use correct Theme property access patterns

**Page Files - Complete Rewrites**
- `EventViewer.qml`: Event monitoring with ListView, status indicators, AlertTriangle integration
- `SystemSnapshot.qml`: System health metrics with GridLayout, hardware/OS information panels
- `ScanHistory.qml`: Scan history table with status badges and ListView delegates
- `NetworkScan.qml`: Network scanning control panel with action buttons
- `ScanTool.qml`: Scan mode selection with GridLayout card interface
- `DataLossPrevention.qml`: DLP metrics dashboard with progress indicators
- `Settings.qml`: Settings management with organized panels

**Component Files - All Fixed**
- `Theme.qml`: Removed incorrect `QtQuick.Singleton` import, fixed pragma Singleton ordering
- `Card.qml`: Updated Theme property access, fixed hover effects and shadows
- `SidebarNav.qml`: Simplified navigation with ListView, removed compact mode complexity
- `TopStatusBar.qml`: Fixed Theme.success, Theme.text property access
- `Panel.qml`: Fixed QtQuick.Effects import, corrected Accessible.role
- `AlertTriangle.qml`: Rebuilt with simple Rectangle/Text pattern, animations working
- All other components: Cleaned of incorrect imports and property references

**Main Application**
- Fixed `main.qml` imports (removed non-existent "theme" directory reference)
- Corrected all `Theme.duration.*` to use `Theme.duration_fast` pattern
- Removed unused `compact` property binding complexity
- Fixed `Theme.bg` color assignment

### 🐛 Bug Fixes
- Fixed "module 'QtQuick.Singleton' is not installed" error
- Fixed "Type Theme unavailable" across all files
- Fixed "Expected token '}'" syntax error in SystemSnapshot.qml
- Fixed "Cannot assign to non-existent property 'compact'" in main.qml
- Fixed "TypeError: Cannot read property 'fast' of undefined" in duration animations
- Fixed "Unable to assign [undefined] to QAccessible::Role" in Panel.qml

### 📦 File Changes
- **Modified**: 7 page files (complete rewrites)
- **Modified**: 14 component files (import and property fixes)
- **Modified**: `main.qml` (import and property corrections)
- **Lines changed**: ~1500+ lines across 22 files

### 🎯 Validation
- Application successfully loads and runs
- All pages accessible via navigation
- Theme singleton correctly resolves across all files
- Only minor Qt style customization warnings (non-blocking, cosmetic)
- Zero critical errors in QML engine

### 📝 Notes
- QML styling warnings about native Windows style are expected and don't affect functionality
- All core features working: navigation, scrolling, layouts, animations
- Ready for production use with pixel-perfect layouts at ≥1100×700 resolution
