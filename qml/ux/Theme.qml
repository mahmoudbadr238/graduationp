import QtQuick
import QtQuick.Window

/**
 * Responsive Theme System with DPI-aware scaling
 * Provides consistent sizing, typography, and spacing across all viewports
 */
pragma Singleton

QtObject {
    id: theme
    
    // DPI/High-DPI scaling
    readonly property real dp: Screen.devicePixelRatio
    readonly property real basePixelSize: Qt.application.font.pixelSize
    
    // Size scale factor (1.0 = 100%, can be adjusted for accessibility)
    property real scaleFactor: 1.0
    
    // SPACING SCALE - responsive to base font size
    // Use these instead of hard-coded pixels
    readonly property int spacing_xs: Math.ceil(basePixelSize * 0.25 * scaleFactor)   // ~3px
    readonly property int spacing_sm: Math.ceil(basePixelSize * 0.5 * scaleFactor)    // ~6px
    readonly property int spacing_md: Math.ceil(basePixelSize * 0.75 * scaleFactor)   // ~9px
    readonly property int spacing_lg: Math.ceil(basePixelSize * 1.0 * scaleFactor)    // ~12px
    readonly property int spacing_xl: Math.ceil(basePixelSize * 1.5 * scaleFactor)    // ~18px
    readonly property int spacing_2xl: Math.ceil(basePixelSize * 2.0 * scaleFactor)   // ~24px
    readonly property int spacing_3xl: Math.ceil(basePixelSize * 3.0 * scaleFactor)   // ~36px
    
    // SIZE SCALE - for icons and small components
    readonly property int size_xs: Math.ceil(16 * dp)      // 16px icons
    readonly property int size_sm: Math.ceil(20 * dp)      // 20px icons
    readonly property int size_md: Math.ceil(24 * dp)      // 24px icons (default)
    readonly property int size_lg: Math.ceil(32 * dp)      // 32px icons
    readonly property int size_xl: Math.ceil(48 * dp)      // 48px icons
    readonly property int size_2xl: Math.ceil(64 * dp)     // 64px icons
    
    // CONTROL SIZE SCALE - buttons, inputs, toggles
    readonly property int control_height_sm: Math.ceil(28 * dp)    // compact buttons
    readonly property int control_height_md: Math.ceil(36 * dp)    // standard buttons
    readonly property int control_height_lg: Math.ceil(44 * dp)    // large buttons
    readonly property int control_height_xl: Math.ceil(56 * dp)    // full-height controls
    
    readonly property int control_width_min: Math.ceil(200 * dp)   // minimum control width (responsive)
    readonly property int control_width_max: Math.ceil(600 * dp)   // maximum control width
    
    // TYPOGRAPHY SYSTEM - responsive font sizing
    readonly property QtObject typography: QtObject {
        readonly property QtObject h1: QtObject {
            readonly property int size: Math.ceil(basePixelSize * 1.8 * scaleFactor)  // ~22px
            readonly property int weight: Font.Bold
            readonly property int lineHeight: Math.ceil(size * 1.4)
        }
        readonly property QtObject h2: QtObject {
            readonly property int size: Math.ceil(basePixelSize * 1.5 * scaleFactor)  // ~18px
            readonly property int weight: Font.DemiBold
            readonly property int lineHeight: Math.ceil(size * 1.3)
        }
        readonly property QtObject h3: QtObject {
            readonly property int size: Math.ceil(basePixelSize * 1.2 * scaleFactor)  // ~15px
            readonly property int weight: Font.Bold
            readonly property int lineHeight: Math.ceil(size * 1.25)
        }
        readonly property QtObject body: QtObject {
            readonly property int size: basePixelSize                                  // ~12px (system default)
            readonly property int weight: Font.Normal
            readonly property int lineHeight: Math.ceil(size * 1.5)
        }
        readonly property QtObject body_large: QtObject {
            readonly property int size: Math.ceil(basePixelSize * 1.1 * scaleFactor)  // ~13px
            readonly property int weight: Font.Normal
            readonly property int lineHeight: Math.ceil(size * 1.5)
        }
        readonly property QtObject caption: QtObject {
            readonly property int size: Math.ceil(basePixelSize * 0.85 * scaleFactor) // ~10px
            readonly property int weight: Font.Normal
            readonly property int lineHeight: Math.ceil(size * 1.4)
        }
        readonly property QtObject label: QtObject {
            readonly property int size: Math.ceil(basePixelSize * 0.9 * scaleFactor)  // ~11px
            readonly property int weight: Font.DemiBold
            readonly property int lineHeight: Math.ceil(size * 1.3)
        }
        readonly property QtObject mono: QtObject {
            readonly property int size: Math.ceil(basePixelSize * 0.9 * scaleFactor)  // ~11px monospace
            readonly property string family: "Courier New"
            readonly property int weight: Font.Normal
        }
    }
    
    // ANIMATION DURATIONS (milliseconds)
    readonly property QtObject duration: QtObject {
        readonly property int fast: 140
        readonly property int medium: 300
        readonly property int slow: 500
    }
    
    // Z-INDEX LAYERS
    readonly property QtObject zIndex: QtObject {
        readonly property int base: 0
        readonly property int overlay: 1000
        readonly property int modal: 2000
        readonly property int toast: 3000
        readonly property int tooltip: 4000
    }
    
    // RESPONSIVE WIDTH BREAKPOINTS (in pixels)
    readonly property QtObject breakpoints: QtObject {
        readonly property int phone_small: 320
        readonly property int phone: 375
        readonly property int phone_large: 414
        readonly property int tablet: 768
        readonly property int laptop: 1024
        readonly property int desktop: 1366
        readonly property int wide: 1920
        readonly property int ultrawide: 2560
    }
    
    // MINIMUM WINDOW SIZES for different viewport modes
    readonly property int window_min_width: 1024    // Never smaller than laptop width
    readonly property int window_min_height: 640    // Minimum vertical space
    
    // Helper function: detect current breakpoint
    function currentBreakpoint(width) {
        if (width < breakpoints.phone_large) return "phone_small"
        if (width < breakpoints.tablet) return "phone"
        if (width < breakpoints.laptop) return "tablet"
        if (width < breakpoints.desktop) return "laptop"
        if (width < breakpoints.wide) return "desktop"
        if (width < breakpoints.ultrawide) return "wide"
        return "ultrawide"
    }
    
    // Helper function: get responsive spacing based on breakpoint
    function spacingForBreakpoint(breakpoint) {
        switch(breakpoint) {
            case "phone_small":
            case "phone":
                return spacing_md
            case "tablet":
                return spacing_lg
            default:
                return spacing_xl
        }
    }
    
    // COLORS (dark theme)
    readonly property color bg: "#0d1117"           // Dark background
    readonly property color bg_secondary: "#161b22"  // Secondary background
    readonly property color panel: "#0d1117"         // Panel background
    readonly property color panel_hover: "#161b22"   // Panel hover state
    readonly property color border: "#30363d"        // Border color
    readonly property color border_subtle: "#21262d" // Subtle border
    
    readonly property color text: "#c9d1d9"          // Primary text
    readonly property color text_secondary: "#8b949e" // Secondary text
    readonly property color text_tertiary: "#6e7681"  // Tertiary text
    readonly property color text_disabled: "#484f58"  // Disabled text
    
    readonly property color primary: "#58a6ff"       // Primary accent (blue)
    readonly property color success: "#3fb950"       // Success (green)
    readonly property color warning: "#d29922"       // Warning (orange)
    readonly property color danger: "#f85149"        // Danger (red)
    readonly property color info: "#79c0ff"          // Info (light blue)
    
    // SHADOWS
    readonly property string shadow_sm: "0 1px 2px rgba(0,0,0,0.1)"
    readonly property string shadow_md: "0 4px 6px rgba(0,0,0,0.1)"
    readonly property string shadow_lg: "0 10px 15px rgba(0,0,0,0.2)"
    readonly property string shadow_xl: "0 20px 25px rgba(0,0,0,0.3)"
}
