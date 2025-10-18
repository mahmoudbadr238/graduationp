# Sentinel - Endpoint Security Suite

## Architecture Overview

This is a **PySide6 + QML desktop security application** with a modern dark theme UI. The architecture separates Python backend (system monitoring via `psutil`) from QML frontend (navigation, theming, UI components).

### Key Components
- **`main.py`**: Entry point that imports and runs `app.application.run()`
- **`app/application.py`**: Core Qt application setup, QML engine configuration, path management
- **`qml/main.qml`**: Root window with sidebar navigation and StackView page routing
- **`qml/components/`**: Reusable UI components with singleton Theme system
- **`qml/pages/`**: Seven security tool pages (EventViewer, SystemSnapshot, ScanHistory, etc.)

## Critical Patterns

### QML Module System
Each directory has a `qmldir` file defining component exports:
```qml
// components/qmldir
singleton Theme 1.0 Theme.qml
Card 1.0 Card.qml
AppSurface 1.0 AppSurface.qml
```

Import components using relative paths: `import "../components"` or `import "../theme"`

### Theme Architecture
**Singleton Theme Pattern**: `Theme.qml` provides centralized design tokens accessible globally:
- Colors: `Theme.bg`, `Theme.panel`, `Theme.text`, `Theme.primary`
- Spacing: `Theme.spacing_md`, `Theme.spacing_lg` 
- Typography: `Theme.typography.h1.size`, `Theme.typography.body.weight`
- Motion: `Theme.duration_fast` for consistent 140ms animations

### Page Navigation
`main.qml` uses a `pageComponents` array with Component wrappers:
```qml
property list<Component> pageComponents: [
    Component { EventViewer {} },
    Component { SystemSnapshot {} }
]
```
Navigation triggers `stackView.replace(pageComponents[index])` with fade transitions.

### Component Patterns
- **AppSurface**: Standard page wrapper with scroll and fade-in animation
- **Card**: Hover-enabled container with 1.02 scale and shadow effects
- **Panel**: Content sections with consistent spacing and title headers
- **SectionHeader**: Text headers with proper implicit sizing (avoid fixed width/height)

## Development Workflow

### Running the Application
```bash
python main.py
```
Requires PySide6 and psutil. Application sets working directory to workspace root and loads `qml/main.qml`.

### Layout Best Practices
- **Grid Layouts**: Use `Layout.preferredWidth/Height` instead of `Layout.fillWidth` for metric cards
- **ScrollView Structure**: Add margins (`anchors.margins: Theme.spacing_md`) and reasonable width constraints
- **Container Sizing**: Use `Math.max(800, parent.width - Theme.spacing_md * 2)` for responsive content width
- **Spacing**: Use `Theme.spacing_lg` between major sections, `Theme.spacing_md` within components

### Adding New Pages
1. Create `qml/pages/NewPage.qml` extending `AppSurface`
2. Add to `qml/pages/qmldir`: `NewPage 1.0 NewPage.qml`
3. Add Component to `main.qml` pageComponents array
4. Add navigation item to `SidebarNav.qml` model

### Creating Components
Follow the Card.qml pattern:
- Use `Theme.*` properties for colors/spacing
- Add Accessible.role and Accessible.name for screen readers
- Include hover states using `hoverable` property and MouseArea
- Use `default property alias children` for content containers
- Set proper `implicitWidth/Height` based on content, avoid fixed dimensions

### Build Script Usage
`build_pages.py` contains template generators for rapid page prototyping - reference for page structure patterns.

## Key Constraints
- **Qt Controls Style**: Set to "Fusion" for full customization (`QT_QUICK_CONTROLS_STYLE=Fusion`)
- **Path Management**: Application changes working directory to workspace root for relative QML imports
- **Admin Privileges**: Warns if not running as administrator (security features limitation)
- **Component Registration**: QML engine adds import paths for `qml/` directory and subdirectories