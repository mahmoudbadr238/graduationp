pragma Singleton
import QtQuick
import QtQuick.Window

QtObject {
    id: themeRoot
    
    // ============================================================
    // RESPONSIVE SCALING SYSTEM
    // ============================================================
    // DPI-aware scaling
    readonly property real dp: Screen.devicePixelRatio ?? 1.0
    readonly property real basePixelSize: Qt.application.font.pixelSize ?? 12
    property real scaleFactor: 1.0  // Can be adjusted for accessibility
    
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
    
    // MINIMUM WINDOW SIZES
    readonly property int window_min_width: 1024
    readonly property int window_min_height: 640
    
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

    // ============================================================
    // THEME MODE MANAGEMENT
    // ============================================================
    property string themeMode: "dark"  // "dark", "light", "system"
    
    function isDark() {
        if (themeMode === "dark") return true
        if (themeMode === "light") return false
        return Qt.styleHints.colorScheme === Qt.Dark
    }

    // ============================================================
    // COLOR PALETTE - Centralized & Reactive
    // ============================================================
    
    // Background colors
    readonly property color bg: isDark() ? "#0f1420" : "#f6f8fc"
    readonly property color panel: isDark() ? "#131A28" : "#ffffff"
    readonly property color surface: isDark() ? "#0C1220" : "#e8ecf4"
    readonly property color elevatedPanel: isDark() ? "#1A2233" : "#f3f4f6"
    
    // Text colors
    readonly property color text: isDark() ? "#e6e9f2" : "#1a1b1e"
    readonly property color textSecondary: isDark() ? "#8B97B0" : "#6c757d"  // Alias for muted
    readonly property color muted: isDark() ? "#8B97B0" : "#6c757d"
    
    // Border colors
    readonly property color border: isDark() ? "#232B3B" : "#d1d5db"
    
    // Accent & semantic colors
    readonly property color primary: "#7C5CFF"
    readonly property color accent: "#6c5ce7"
    readonly property color info: "#3B82F6"
    readonly property color success: "#22C55E"
    readonly property color warning: "#F59E0B"
    readonly property color danger: "#EF4444"
    readonly property color error: "#EF4444"  // Alias for danger
    
    // Glass/Neon effects
    readonly property color purpleGlow: "#7C5CFF44"
    readonly property color gradientStart: "#7C5CFF11"
    readonly property color gradientEnd: "#7C5CFF05"
    
    // Focus ring
    readonly property color focusRing: primary
    readonly property int focusRingWidth: 2
    readonly property int focusRingRadius: 8

    // ============================================================
    // SPACING SYSTEM (8px base unit)
    // ============================================================
    readonly property int unit: 8
    
    readonly property int spacing_xs: 6    // 0.75 units
    readonly property int spacing_sm: 10   // 1.25 units
    readonly property int spacing_md: 16   // 2 units (default)
    readonly property int spacing_lg: 24   // 3 units
    readonly property int spacing_xl: 32   // 4 units
    readonly property int spacing_xxl: 48  // 6 units
    
    // Legacy aliases (for backward compatibility)
    readonly property int gap: spacing_md
    
    // Nested spacing object (modern API)
    readonly property QtObject spacing: QtObject {
        readonly property int xs: spacing_xs
        readonly property int sm: spacing_sm
        readonly property int md: spacing_md
        readonly property int lg: spacing_lg
        readonly property int xl: spacing_xl
        readonly property int xxl: spacing_xxl
    }

    // ============================================================
    // BORDER RADIUS SYSTEM
    // ============================================================
    readonly property int radii_xs: 4
    readonly property int radii_sm: 8
    readonly property int radii_md: 12
    readonly property int radii_lg: 18
    readonly property int radii_xl: 24
    readonly property int radii_full: 9999

    // Legacy alias
    readonly property int radius: radii_lg

    // Nested radii object (modern API)
    readonly property QtObject radii: QtObject {
        readonly property int xs: radii_xs
        readonly property int sm: radii_sm
        readonly property int md: radii_md
        readonly property int lg: radii_lg
        readonly property int xl: radii_xl
        readonly property int full: radii_full
        readonly property int pill: radii_full  // Pill shape = fully rounded
    }    // ============================================================
    // TYPOGRAPHY SYSTEM
    // ============================================================
    readonly property QtObject typography: QtObject {
        // Headings
        readonly property QtObject h1: QtObject {
            readonly property int size: 32
            readonly property int weight: Font.DemiBold
            readonly property real lineHeight: 1.25
        }
        readonly property QtObject h2: QtObject {
            readonly property int size: 24
            readonly property int weight: Font.Medium
            readonly property real lineHeight: 1.3
        }
        readonly property QtObject h3: QtObject {
            readonly property int size: 20
            readonly property int weight: Font.Medium
            readonly property real lineHeight: 1.4
        }
        readonly property QtObject h4: QtObject {
            readonly property int size: 18
            readonly property int weight: Font.Medium
            readonly property real lineHeight: 1.4
        }
        
        // Body text
        readonly property QtObject body: QtObject {
            readonly property int size: 15
            readonly property int weight: Font.Normal
            readonly property real lineHeight: 1.5
        }
        readonly property QtObject bodySmall: QtObject {
            readonly property int size: 13
            readonly property int weight: Font.Normal
            readonly property real lineHeight: 1.5
        }
        readonly property QtObject bodyLarge: QtObject {
            readonly property int size: 17
            readonly property int weight: Font.Normal
            readonly property real lineHeight: 1.5
        }
        
        // Monospace
        readonly property QtObject mono: QtObject {
            readonly property int size: 13
            readonly property int weight: Font.Medium
            readonly property string family: "Consolas, 'Courier New', monospace"
        }
        
        // Labels/Captions
        readonly property QtObject label: QtObject {
            readonly property int size: 12
            readonly property int weight: Font.Medium
            readonly property real lineHeight: 1.4
        }
        readonly property QtObject caption: QtObject {
            readonly property int size: 11
            readonly property int weight: Font.Normal
            readonly property real lineHeight: 1.3
        }
    }

    // ============================================================
    // ANIMATION/MOTION SYSTEM
    // ============================================================
    readonly property int duration_instant: 0
    readonly property int duration_fast: 140
    readonly property int duration_medium: 250
    readonly property int duration_slow: 400
    readonly property int duration_stagger: 40
    
    // Nested duration object (modern API)
    readonly property QtObject duration: QtObject {
        readonly property int instant: duration_instant
        readonly property int fast: duration_fast
        readonly property int medium: duration_medium
        readonly property int slow: duration_slow
        readonly property int stagger: duration_stagger
    }
    
    // Easing curves
    readonly property QtObject easing: QtObject {
        readonly property int standard: Easing.InOutQuad
        readonly property int decelerate: Easing.OutCubic
        readonly property int accelerate: Easing.InCubic
        readonly property int sharp: Easing.InOutCubic
    }

    // ============================================================
    // Z-INDEX SYSTEM
    // ============================================================
    readonly property QtObject zIndex: QtObject {
        readonly property int base: 0
        readonly property int dropdown: 1000
        readonly property int sticky: 1100
        readonly property int overlay: 1300
        readonly property int modal: 1400
        readonly property int popover: 1500
        readonly property int toast: 1600
        readonly property int tooltip: 1700
    }

    // ============================================================
    // GLASS/NEON EFFECTS (for glassmorphic panels)
    // ============================================================
    readonly property QtObject glass: QtObject {
        readonly property color panel: Qt.rgba(0.07, 0.1, 0.16, 0.6)
        readonly property color overlay: Qt.rgba(0.1, 0.1, 0.15, 0.4)
        readonly property color card: Qt.rgba(0.1, 0.15, 0.2, 0.5)
        readonly property color border: Qt.rgba(0.49, 0.36, 1.0, 0.15)
        readonly property color borderActive: Qt.rgba(0.49, 0.36, 1.0, 0.3)
        readonly property color gradientStart: "#7C5CFF11"
        readonly property color gradientEnd: "#7C5CFF05"
    }
    
    readonly property QtObject neon: QtObject {
        readonly property color purple: "#7C5CFF"
        readonly property color blue: "#3B82F6"
        readonly property color green: "#22C55E"
        readonly property color purpleGlow: "#7C5CFF44"
        readonly property color blueGlow: "#3B82F644"
        readonly property color greenGlow: "#22C55E44"
        readonly property color purpleDim: "#7C5CFF22"  // Dimmed purple for backgrounds
        readonly property color blueDim: "#3B82F622"
        readonly property color greenDim: "#22C55E22"
    }

    // ============================================================
    // SHADOWS
    // ============================================================
    readonly property QtObject shadow: QtObject {
        readonly property int sm: 2
        readonly property int md: 4
        readonly property int lg: 8
        readonly property int xl: 16
        readonly property color color: "#00000033"
        readonly property real opacity: 0.18
    }

    // ============================================================
    // COMPONENT-SPECIFIC TOKENS
    // ============================================================
    
    // Buttons
    readonly property QtObject button: QtObject {
        readonly property int height: 40
        readonly property int heightSmall: 32
        readonly property int heightLarge: 48
        readonly property int paddingX: spacing_md
        readonly property int paddingY: spacing_sm
    }
    
    // Cards
    readonly property QtObject card: QtObject {
        readonly property int padding: spacing_md
        readonly property int radius: radii_md
        readonly property real hoverScale: 1.02
    }
    
    // Panels
    readonly property QtObject panel_config: QtObject {
        readonly property int padding: spacing_lg
        readonly property int radius: radii_lg
    }
    
    // ============================================================
    // RESPONSIVE CONTROL SIZING
    // ============================================================
    // Control height scale (responsive to DPI and base font)
    readonly property int control_height_sm: Math.ceil(28 * dp)    // compact
    readonly property int control_height_md: Math.ceil(36 * dp)    // standard
    readonly property int control_height_lg: Math.ceil(44 * dp)    // large
    readonly property int control_height_xl: Math.ceil(56 * dp)    // full-height
    
    // Minimum control widths
    readonly property int control_width_min: Math.ceil(200 * dp)
    readonly property int control_width_max: Math.ceil(600 * dp)
    
    // ============================================================
    // TEXT CONFIGURATION
    // ============================================================
    // Standard text wrapping for responsive layouts
    readonly property int text_wrap_mode: Text.WordWrap
    readonly property bool text_elide_enabled: true
}