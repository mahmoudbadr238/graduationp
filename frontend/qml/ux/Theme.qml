import QtQuick
import QtQuick.Window

/**
 * Responsive Theme System with DPI-aware scaling
 * Provides consistent sizing, typography, and spacing across all viewports
 */
pragma Singleton

QtObject {
    id: theme
    
    // BASE UNITS - all responsive to screen and system settings
    readonly property real base: Qt.application.font.pixelSize  // System font size (typically 12px)
    readonly property real dp: Screen.devicePixelRatio          // DPI scale factor
    
    // SPACING SCALE - responsive multipliers of base font size
    readonly property int spacing_xs: Math.ceil(base * 0.6)    // 7-8px
    readonly property int spacing_s: Math.ceil(base * 0.75)    // 9-10px
    readonly property int spacing_m: Math.ceil(base * 1.0)     // 12px
    readonly property int spacing_l: Math.ceil(base * 1.25)    // 15px
    readonly property int spacing_xl: Math.ceil(base * 1.5)    // 18px
    
    // TYPOGRAPHY - responsive based on base font size
    readonly property QtObject type: QtObject {
        readonly property int h1: Math.ceil(base * 2.0)        // 24px heading
        readonly property int h2: Math.ceil(base * 1.75)       // 21px
        readonly property int h3: Math.ceil(base * 1.5)        // 18px
        readonly property int h4: Math.ceil(base * 1.25)       // 15px
        readonly property int body: base                         // 12px
        readonly property int body_sm: Math.ceil(base * 0.92)  // 11px
        readonly property int body_xs: Math.ceil(base * 0.83)  // 10px
    }
    
    // CONTROL SIZES - responsive based on DPI
    readonly property int control_height_sm: Math.ceil(24 * dp)
    readonly property int control_height_md: Math.ceil(32 * dp)
    readonly property int control_height_lg: Math.ceil(40 * dp)
    
    // MIN/MAX SIZES for layouts
    readonly property int min_width: 320        // Minimum sensible width
    readonly property int min_card_width: 280   // Minimum card width for grids
    readonly property int max_content_width: 1200  // Max width for content containers
    
    // ANIMATION
    readonly property int animation_fast: 100
    readonly property int animation_normal: 200
    readonly property int animation_slow: 300
    
    // COLORS (dark theme - from existing)
    readonly property color bg: "#0d1117"
    readonly property color panel: "#131A28"
    readonly property color text: "#e6e9f2"
    readonly property color text_secondary: "#8B97B0"
    readonly property color border: "#232B3B"
    readonly property color primary: "#7C5CFF"
    readonly property color success: "#22C55E"
    readonly property color warning: "#F59E0B"
    readonly property color danger: "#EF4444"
}
