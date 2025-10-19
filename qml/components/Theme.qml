pragma Singleton
import QtQuick 2.15
import "../ui"

Item {
    id: themeRoot
    
    // Color tokens - reactive bindings to ThemeManager
    readonly property color bg: ThemeManager.background()
    readonly property color panel: ThemeManager.panel()
    readonly property color surface: ThemeManager.surface()
    readonly property color text: ThemeManager.foreground()
    readonly property color muted: ThemeManager.muted()
    readonly property color primary: "#7C5CFF"
    readonly property color info: "#3B82F6"
    readonly property color success: "#22C55E"
    readonly property color warning: "#F59E0B"
    readonly property color danger: "#EF4444"
    readonly property color border: ThemeManager.border()
    readonly property color elevatedPanel: ThemeManager.elevated()

    // Focus ring
    readonly property color focusRing: primary
    readonly property int focusRingWidth: 2
    readonly property int focusRingRadius: 8

    // Radii
    readonly property int radius: 18
    readonly property int radii_sm: 8
    readonly property int radii_md: 12
    readonly property int radii_lg: 18

    // Spacing/gap
    readonly property int gap: 16
    readonly property int spacing_xs: 6
    readonly property int spacing_sm: 10
    readonly property int spacing_md: 16
    readonly property int spacing_lg: 24

    // Typography
    readonly property var typography: {
        "h1": {"size": 32, "weight": Font.DemiBold},
        "h2": {"size": 22, "weight": Font.Medium},
        "body": {"size": 15, "weight": Font.Normal},
        "mono": {"size": 13, "weight": Font.Medium}
    }

    // Motion
    readonly property int duration_fast: 140
    readonly property int duration_stagger: 40

    // Theme mode - synced with ThemeManager
    readonly property bool isDark: ThemeManager.isDark()
}
