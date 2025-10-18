# Contributing to Sentinel

Thank you for considering contributing to Sentinel! This document provides guidelines and instructions for contributing.

## 🤝 Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what is best for the community
- Show empathy towards other community members

## 🐛 Reporting Bugs

Before creating bug reports, please check existing issues. When creating a bug report, include:

- **Clear title** describing the issue
- **Steps to reproduce** the behavior
- **Expected behavior** vs actual behavior
- **Screenshots** if applicable
- **Environment details:**
  - OS version (Windows 10/11)
  - Python version
  - PySide6 version

## 💡 Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion:

- **Use a clear and descriptive title**
- **Provide detailed description** of the suggested enhancement
- **Explain why this enhancement would be useful**
- **Include mockups or examples** if applicable

## 🔧 Development Setup

1. **Fork and clone the repository**
```bash
git clone https://github.com/yourusername/sentinel.git
cd sentinel
```

2. **Create virtual environment**
```bash
python -m venv .venv
.venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Run the application**
```bash
python main.py
```

## 📝 Pull Request Process

1. **Create a feature branch**
```bash
git checkout -b feature/amazing-feature
```

2. **Make your changes**
   - Follow the code style (PEP 8 for Python, QML style guide for QML)
   - Add comments for complex logic
   - Update documentation if needed

3. **Test your changes**
   - Test in both dark and light themes
   - Verify all pages work correctly
   - Check keyboard shortcuts still work
   - Test on Windows 10 and 11 if possible

4. **Commit your changes**
```bash
git add .
git commit -m "Add: Brief description of changes"
```

Use conventional commit messages:
- `Add:` for new features
- `Fix:` for bug fixes
- `Update:` for updates to existing features
- `Refactor:` for code refactoring
- `Docs:` for documentation changes
- `Style:` for formatting changes

5. **Push to your fork**
```bash
git push origin feature/amazing-feature
```

6. **Open a Pull Request**
   - Provide clear description of changes
   - Reference related issues
   - Include screenshots for UI changes

## 🎨 Code Style Guidelines

### Python
- Follow PEP 8 style guide
- Use type hints where applicable
- Keep functions focused and small
- Add docstrings for public functions

### QML
- Use 4-space indentation
- Use Theme properties instead of hardcoded colors
- Add Accessible properties for screen readers
- Include smooth transitions (Behavior on color)
- Follow component naming conventions

### Component Structure
```qml
import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    
    // Properties first
    property string title: ""
    
    // Appearance
    color: Theme.panel
    radius: Theme.radii_md
    
    // Behavior animations
    Behavior on color {
        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
    }
    
    // Content
    Text {
        text: root.title
        color: Theme.text
    }
}
```

## 🏗️ Project Architecture

### Directory Structure
- `app/` - Python backend (Qt application, system monitoring)
- `qml/` - QML frontend (UI components, pages)
  - `components/` - Reusable UI components
  - `pages/` - Application pages
  - `theme/` - Theme definitions
  - `ui/` - UI managers
- `docs/` - Documentation
- `.github/` - GitHub workflows and configuration

### Adding New Components

1. Create component in `qml/components/YourComponent.qml`
2. Export in `qml/components/qmldir`:
```qml
YourComponent 1.0 YourComponent.qml
```
3. Use Theme properties for colors
4. Add accessibility properties

### Adding New Pages

1. Create page in `qml/pages/YourPage.qml`
2. Extend AppSurface for consistent layout
3. Add to `qml/pages/qmldir`
4. Add Component to `main.qml` pageComponents
5. Add navigation item to `SidebarNav.qml`

## ✅ Testing Checklist

Before submitting PR:
- [ ] Code follows style guidelines
- [ ] Tested in dark mode
- [ ] Tested in light mode
- [ ] Tested in system mode
- [ ] All pages navigate correctly
- [ ] Keyboard shortcuts work
- [ ] No console errors
- [ ] Smooth animations
- [ ] Accessible (screen reader friendly)
- [ ] Documentation updated
- [ ] CHANGELOG.md updated

## 📚 Resources

- [Qt for Python Documentation](https://doc.qt.io/qtforpython/)
- [QML Documentation](https://doc.qt.io/qt-6/qmlapplications.html)
- [PySide6 Examples](https://doc.qt.io/qtforpython/examples/)
- [psutil Documentation](https://psutil.readthedocs.io/)

## 💬 Questions?

Feel free to open an issue for questions or discussion.

---

Thank you for contributing! 🙏
