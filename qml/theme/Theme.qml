pragma Singleton
import QtQuick

QtObject {
    readonly property QtObject colors: QtObject {
        readonly property color background: "#0F1420"
        readonly property color panel: "#131A28"
        readonly property color text: "#E6EBFF"
        readonly property color muted: "#8B97B0"
        readonly property color primary: "#7C5CFF"
        readonly property color success: "#22C55E"
        readonly property color warning: "#F97316"
        readonly property color error: "#EF4444"
        readonly property color elevatedPanel: "#1A2235"
        readonly property color border: "#1F2937"
    }
    
    readonly property QtObject typography: QtObject {
        readonly property QtObject h1: QtObject {
            readonly property int size: 32
            readonly property int weight: 600
        }
        readonly property QtObject h2: QtObject {
            readonly property int size: 24
            readonly property int weight: 500
        }
        readonly property QtObject body: QtObject {
            readonly property int size: 14
            readonly property int weight: 400
        }
    }
    
    readonly property QtObject spacing: QtObject {
        readonly property int xs: 4
        readonly property int sm: 8
        readonly property int md: 16
        readonly property int lg: 24
        readonly property int outer: 24
        readonly property int inner: 16
    }
    
    readonly property QtObject radii: QtObject {
        readonly property int card: 18
        readonly property int sm: 8
        readonly property int md: 12
    }
    
    readonly property QtObject duration: QtObject {
        readonly property int fast: 150
        readonly property int medium: 250
        readonly property int slow: 350
        readonly property int stagger: 40
    }
    
    readonly property QtObject breakpoints: QtObject {
        readonly property int desktop: 1280
    }
}
