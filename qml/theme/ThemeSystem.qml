pragma Singleton
import QtQuick

QtObject {
    id: themeSystem

    // Externally set from SettingsService
    property string themeMode: "dark"
    
    // Internal color properties
    property color windowBackground
    property color sidebarBackground
    property color surface
    property color surfaceAlt
    property color accent
    property color accentSoft
    property color textPrimary
    property color textSecondary
    property color textAccent
    property color borderSubtle
    property color borderStrong
    property color success
    property color warning
    property color error
    property color errorLight

    // Metrics
    readonly property int cardRadius: 14
    readonly property int cardPadding: 14
    readonly property int pagePadding: 24
    readonly property int sectionSpacing: 24
    readonly property int itemSpacing: 12
    readonly property int rowSpacing: 8

    function updateColors() {
        if (themeMode === "dark") {
            windowBackground = "#050712"
            sidebarBackground = "#070A18"
            surface = "#101425"
            surfaceAlt = "#14192B"
            accent = "#8b5cf6"
            accentSoft = "#241447"
            textPrimary = "#F9FAFB"
            textSecondary = "#9CA3AF"
            textAccent = "#C4B5FD"
            borderSubtle = "#1F2933"
            borderStrong = "#2D3B54"
            success = "#34D399"
            warning = "#FBBF24"
            error = "#F97373"
            errorLight = "#FEE2E2"
        } else {
            windowBackground = "#F3F4F6"
            sidebarBackground = "#FFFFFF"
            surface = "#FFFFFF"
            surfaceAlt = "#F9FAFB"
            accent = "#7C3AED"
            accentSoft = "#EDE9FE"
            textPrimary = "#111827"
            textSecondary = "#6B7280"
            textAccent = "#4C1D95"
            borderSubtle = "#E5E7EB"
            borderStrong = "#D1D5DB"
            success = "#16A34A"
            warning = "#D97706"
            error = "#DC2626"
            errorLight = "#FEE2E2"
        }
    }

    onThemeModeChanged: updateColors()

    Component.onCompleted: {
        if (typeof SettingsService !== 'undefined' && SettingsService) {
            themeMode = SettingsService.themeMode
        }
        updateColors()
    }
}
