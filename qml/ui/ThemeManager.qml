pragma Singleton
import QtQuick 2.15

QtObject {
    id: themeManager
    
    property string themeMode: "system"  // "dark", "light", "system"
    
    // Color palette
    readonly property color accent: "#6c5ce7"
    readonly property color darkBg: "#0f1420"
    readonly property color lightBg: "#f6f8fc"
    readonly property color darkText: "#e6e9f2"
    readonly property color lightText: "#1a1b1e"
    readonly property color darkPanel: "#131A28"
    readonly property color lightPanel: "#ffffff"
    readonly property color darkSurface: "#0C1220"
    readonly property color lightSurface: "#e8ecf4"
    readonly property color darkMuted: "#8B97B0"
    readonly property color lightMuted: "#6c757d"
    readonly property color darkBorder: "#232B3B"
    readonly property color lightBorder: "#d1d5db"
    readonly property color darkElevated: "#1A2233"
    readonly property color lightElevated: "#f3f4f6"
    
    // Success/Warning/Danger (same for both themes)
    readonly property color success: "#22C55E"
    readonly property color warning: "#F59E0B"
    readonly property color danger: "#EF4444"
    readonly property color info: accent
    
    function isDark() {
        if (themeMode === "dark") return true
        if (themeMode === "light") return false
        // System preference
        return Qt.styleHints.colorScheme === Qt.Dark
    }
    
    function background() { return isDark() ? darkBg : lightBg }
    function foreground() { return isDark() ? darkText : lightText }
    function panel() { return isDark() ? darkPanel : lightPanel }
    function surface() { return isDark() ? darkSurface : lightSurface }
    function muted() { return isDark() ? darkMuted : lightMuted }
    function border() { return isDark() ? darkBorder : lightBorder }
    function elevated() { return isDark() ? darkElevated : lightElevated }
    
    // Focus ring styling
    readonly property int focusRingWidth: 2
    readonly property color focusRingColor: accent
    readonly property int focusRingRadius: 8
    
    // Selection colors
    readonly property color selectionBackground: accent
    readonly property color selectionForeground: "#ffffff"
}
