pragma Singleton
import QtQuick 2.15

QtObject {
    id: themeManager
    
    property string themeMode: "system"  // "dark", "light", "system"
    property string fontSize: "medium"  // "small", "medium", "large"
    property int fontSizeUpdateTrigger: 0  // Trigger for UI updates
    property bool _initialized: false
    property int _retryCount: 0
    property int _maxRetries: 10
    
    // Timer for retrying initialization
    property Timer _initTimer: Timer {
        interval: 100
        repeat: false
        onTriggered: themeManager.initializeTheme()
    }
    
    // Connect to SettingsService on startup with retry logic
    function initializeTheme() {
        if (_initialized) return
        
        if (typeof SettingsService !== 'undefined' && SettingsService) {
            // Load from settings
            var loadedTheme = SettingsService.themeMode
            var loadedFontSize = SettingsService.fontSize
            
            console.log("[ThemeManager] Loaded themeMode:", loadedTheme)
            console.log("[ThemeManager] Loaded fontSize:", loadedFontSize)
            
            themeMode = loadedTheme
            fontSize = loadedFontSize
            _initialized = true
            
            // Connect for changes
            try {
                SettingsService.themeModeChanged.connect(onThemeModeChanged)
                SettingsService.fontSizeChanged.connect(onFontSizeChanged)
                console.log("[ThemeManager] Connected to SettingsService signals")
            } catch(e) {
                console.warn("[ThemeManager] Could not connect to SettingsService signals:", e)
            }
        } else {
            // SettingsService not ready yet, retry after a short delay
            _retryCount++
            if (_retryCount < _maxRetries) {
                console.log("[ThemeManager] SettingsService not ready, retry", _retryCount)
                _initTimer.start()
            } else {
                console.warn("[ThemeManager] Failed to connect to SettingsService after", _maxRetries, "retries")
            }
        }
    }
    
    function onThemeModeChanged() {
        if (typeof SettingsService !== 'undefined' && SettingsService) {
            themeMode = SettingsService.themeMode
        }
    }
    
    function onFontSizeChanged() {
        if (typeof SettingsService !== 'undefined' && SettingsService) {
            fontSize = SettingsService.fontSize
        }
        // Trigger re-render by changing this counter
        fontSizeUpdateTrigger = fontSizeUpdateTrigger + 1
    }
    
    function setThemeMode(mode) {
        themeMode = mode
        if (typeof SettingsService !== 'undefined' && SettingsService) {
            SettingsService.themeMode = mode
        }
    }
    
    function setFontSize(size) {
        fontSize = size
        if (typeof SettingsService !== 'undefined' && SettingsService) {
            SettingsService.fontSize = size
        }
        // Trigger re-render
        fontSizeUpdateTrigger = fontSizeUpdateTrigger + 1
    }
    
    function getFontScale() {
        if (fontSize === "small") return 0.85
        if (fontSize === "large") return 1.15
        return 1.0  // medium
    }
    
    // Font size helpers
    function fontSize_h1() { return Math.round(28 * getFontScale()) }
    function fontSize_h2() { return Math.round(22 * getFontScale()) }
    function fontSize_h3() { return Math.round(18 * getFontScale()) }
    function fontSize_body() { return Math.round(14 * getFontScale()) }
    function fontSize_small() { return Math.round(12 * getFontScale()) }
    
    Component.onCompleted: {
        initializeTheme()
    }
    
    // Color palette
    readonly property color accent: "#7C3AED"
    readonly property color darkBg: "#050814"
    readonly property color lightBg: "#f6f8fc"
    readonly property color darkText: "#F9FAFB"
    readonly property color lightText: "#1a1b1e"
    readonly property color darkPanel: "#0B1020"
    readonly property color lightPanel: "#ffffff"
    readonly property color darkSurface: "#050814"
    readonly property color lightSurface: "#e8ecf4"
    readonly property color darkMuted: "#9CA3AF"
    readonly property color lightMuted: "#6c757d"
    readonly property color darkBorder: "#1F2937"
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
