pragma Singleton
import QtQuick
import "../ui"

QtObject {
    // Dynamic colors based on ThemeManager
    
    // Background colors
    readonly property color background: ThemeManager.background()
    readonly property color panel: ThemeManager.panel()
    readonly property color surface: ThemeManager.surface()
    readonly property color elevated: ThemeManager.elevated()
    
    // Text colors
    readonly property color text: ThemeManager.foreground()
    readonly property color textMuted: ThemeManager.muted()
    readonly property color textInverted: ThemeManager.isDark() ? "#050814" : "#F9FAFB"
    
    // Border colors
    readonly property color border: ThemeManager.border()
    readonly property color borderLight: ThemeManager.isDark() ? "#374151" : "#D1D5DB"
    
    // UI colors
    readonly property color accent: "#7C3AED"
    readonly property color success: "#22C55E"
    readonly property color warning: "#F59E0B"
    readonly property color danger: "#EF4444"
    readonly property color info: "#3B82F6"
}
