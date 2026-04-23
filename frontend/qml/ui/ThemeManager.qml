pragma Singleton
import QtQuick 2.15

QtObject {
    id: themeManager
    
    property string themeMode: "system"  // "dark", "light", "system"
    property string fontSize: "medium"  // "small", "medium", "large"
    property int fontSizeUpdateTrigger: 0  // Trigger for UI updates
    property int themeModeUpdateTrigger: 0  // Trigger for theme re-render
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
            var loadedTheme = (SettingsService.themeMode || "system").toString().trim().toLowerCase()
            var loadedFontSize = SettingsService.fontSize

            themeMode = loadedTheme
            fontSize = loadedFontSize
            _initialized = true

            try {
                SettingsService.themeModeChanged.connect(onThemeModeChanged)
                SettingsService.fontSizeChanged.connect(onFontSizeChanged)
            } catch(e) {
                console.warn("[ThemeManager] Could not connect to SettingsService signals:", e)
            }
        } else {
            _retryCount++
            if (_retryCount < _maxRetries) {
                _initTimer.start()
            } else {
                console.warn("[ThemeManager] SettingsService unavailable after", _maxRetries, "retries — using defaults")
            }
        }
    }
    
    function onThemeModeChanged() {
        if (typeof SettingsService !== 'undefined' && SettingsService) {
            themeMode = (SettingsService.themeMode || "system").toString().trim().toLowerCase()
        }
        // Trigger re-render by changing this counter
        themeModeUpdateTrigger = themeModeUpdateTrigger + 1
        themeManager.themeModeChanged()
    }
    
    function onFontSizeChanged() {
        if (typeof SettingsService !== 'undefined' && SettingsService) {
            fontSize = SettingsService.fontSize
        }
        // Trigger re-render by changing this counter
        fontSizeUpdateTrigger = fontSizeUpdateTrigger + 1
    }
    
    function setThemeMode(mode) {
        // Normalize and apply user-chosen theme
        mode = (mode || "system").toString().trim().toLowerCase()
        themeMode = mode
        if (typeof SettingsService !== 'undefined' && SettingsService) {
            SettingsService.themeMode = mode
        }
        // Trigger re-render
        themeModeUpdateTrigger = themeModeUpdateTrigger + 1
        themeManager.themeModeChanged()
    }
    
    function setFontSize(size) {
        fontSize = size
        if (typeof SettingsService !== 'undefined' && SettingsService) {
            SettingsService.fontSize = size
        }
        // Trigger re-render
        fontSizeUpdateTrigger = fontSizeUpdateTrigger + 1
        themeManager.fontSizeChanged()
    }
    
    function getFontScale() {
        if (fontSize === "small") return 0.85
        if (fontSize === "large") return 1.15
        return 1.0  // medium
    }

    // ── Reactive font-scale factor (property, not function) ──
    // Every property below depends on `fontSize`, so QML re-evaluates
    // all bindings automatically when the user changes the font setting.
    readonly property real fontScale: fontSize === "small" ? 0.85
                                    : fontSize === "large" ? 1.15
                                    : 1.0

    // ── Reactive font-size properties (replace broken function calls) ──
    readonly property int fontSize_h1:    Math.round(28 * fontScale)
    readonly property int fontSize_h2:    Math.round(22 * fontScale)
    readonly property int fontSize_h3:    Math.round(18 * fontScale)
    readonly property int fontSize_body:  Math.round(14 * fontScale)
    readonly property int fontSize_small: Math.round(12 * fontScale)

    // Additional hierarchy levels used by some components
    readonly property int fontSize_h4:       Math.round(16 * fontScale)
    readonly property int fontSize_bodyLarge: Math.round(16 * fontScale)
    readonly property int fontSize_caption:   Math.round(10 * fontScale)
    
    Component.onCompleted: {
        initializeTheme()
    }
    
    // Color palette
    readonly property color accent: "#7C3AED"
    readonly property color primary: accent  // Alias for accent
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
