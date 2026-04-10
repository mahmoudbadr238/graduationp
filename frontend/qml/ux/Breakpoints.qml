import QtQuick

/**
 * Responsive breakpoint detector
 * Pass the window/parent width and get boolean flags for current breakpoint
 * Usage:
 *   Breakpoints { w: parent.width }
 *   visible: breakpoints.md  // Only show on medium+ screens
 */
QtObject {
    id: bp
    
    // Input: pass the width to monitor
    property int w: 1024
    
    // Breakpoint flags (true if current width is in this range)
    readonly property bool xs: w < 640       // Extra small (phones, < 640px)
    readonly property bool sm: w >= 640 && w < 1024   // Small (tablets, 640-1024px)
    readonly property bool md: w >= 1024 && w < 1440  // Medium (small laptops, 1024-1440px)
    readonly property bool lg: w >= 1440 && w < 1920  // Large (desktops, 1440-1920px)
    readonly property bool xl: w >= 1920     // Extra large (wide/ultrawide, 1920px+)
    
    // Convenience flags
    readonly property bool mobile: xs || sm
    readonly property bool desktop: md || lg || xl
    readonly property bool wide: lg || xl
    
    // Size hints
    readonly property int columns: {
        if (xs) return 1
        if (sm) return 2
        if (md) return 2
        if (lg) return 3
        return 4
    }
    
    readonly property int columnWidth: {
        if (xs) return w - 16
        if (sm) return Math.floor((w - 24) / 2) - 8
        if (md) return Math.floor((w - 32) / 2) - 8
        if (lg) return Math.floor((w - 40) / 3) - 10
        return Math.floor((w - 48) / 4) - 12
    }
}
