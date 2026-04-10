import QtQuick
import QtQuick.Controls
import "../ui"

Item {
    id: root
    
    // Public properties
    property bool live: true
    property color strokeColor: ThemeManager.isDark() ? "#4B5563" : "#9CA3AF"
    property color activeColor: ThemeManager.isDark() ? "#7C3AED" : "#8B5CF6"
    property real lineWidth: 3.0
    
    // Animation progress: 0 to 3 represents traversing all 3 edges
    property real edgeProgress: 0.0
    
    // Edge tracing animation
    NumberAnimation on edgeProgress {
        id: edgeAnimation
        from: 0
        to: 3
        duration: 3000
        loops: Animation.Infinite
        running: root.live
        easing.type: Easing.Linear
    }
    
    // Glow intensity based on progress (peaks at each edge midpoint)
    property real glowIntensity: {
        var p = edgeProgress % 1.0
        return 0.5 + Math.sin(p * Math.PI) * 0.5
    }
    
    // Background is transparent
    Rectangle {
        anchors.fill: parent
        color: "transparent"
    }
    
    // Main canvas for the triangle
    Canvas {
        id: triangleCanvas
        anchors.fill: parent
        anchors.margins: 10
        
        property real progress: root.edgeProgress
        property color baseColor: root.strokeColor
        property color activeCol: root.activeColor
        property real lineW: root.lineWidth
        property bool isLive: root.live
        property real glow: root.glowIntensity
        
        onProgressChanged: requestPaint()
        onBaseColorChanged: requestPaint()
        onActiveColChanged: requestPaint()
        onLineWChanged: requestPaint()
        onIsLiveChanged: requestPaint()
        onGlowChanged: requestPaint()
        
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            
            var w = width
            var h = height
            
            // Calculate equilateral triangle vertices with margin
            var margin = lineW * 2
            var centerX = w / 2
            var centerY = h / 2
            
            // Triangle dimensions (equilateral)
            var triHeight = h - margin * 2
            var triWidth = triHeight * (2 / Math.sqrt(3))
            
            // Adjust if triangle is too wide
            if (triWidth > w - margin * 2) {
                triWidth = w - margin * 2
                triHeight = triWidth * (Math.sqrt(3) / 2)
            }
            
            // Vertices: top, bottom-right, bottom-left
            var topX = centerX
            var topY = centerY - triHeight / 2
            var bottomRightX = centerX + triWidth / 2
            var bottomRightY = centerY + triHeight / 2
            var bottomLeftX = centerX - triWidth / 2
            var bottomLeftY = centerY + triHeight / 2
            
            // Edge definitions
            var edges = [
                { x1: topX, y1: topY, x2: bottomRightX, y2: bottomRightY },      // Edge 0: top to bottom-right
                { x1: bottomRightX, y1: bottomRightY, x2: bottomLeftX, y2: bottomLeftY }, // Edge 1: bottom-right to bottom-left
                { x1: bottomLeftX, y1: bottomLeftY, x2: topX, y2: topY }         // Edge 2: bottom-left to top
            ]
            
            // Draw base triangle outline (dim)
            ctx.beginPath()
            ctx.moveTo(topX, topY)
            ctx.lineTo(bottomRightX, bottomRightY)
            ctx.lineTo(bottomLeftX, bottomLeftY)
            ctx.closePath()
            
            ctx.strokeStyle = baseColor
            ctx.lineWidth = lineW
            ctx.lineJoin = "round"
            ctx.lineCap = "round"
            ctx.globalAlpha = isLive ? 0.3 : 0.5
            ctx.stroke()
            
            // If not live, just show the dim outline
            if (!isLive) {
                return
            }
            
            // Draw the active scanning segment
            ctx.globalAlpha = 1.0
            
            // Determine which edge we're on and how far along
            var currentEdge = Math.floor(progress)
            var edgeFraction = progress - currentEdge
            
            // Clamp to valid range
            if (currentEdge >= 3) {
                currentEdge = 2
                edgeFraction = 1.0
            }
            
            var edge = edges[currentEdge]
            
            // Calculate the active segment (a portion of the edge that's highlighted)
            // The "scanner" is about 30% of each edge length
            var scannerLength = 0.35
            var scannerStart = Math.max(0, edgeFraction - scannerLength)
            var scannerEnd = edgeFraction
            
            // Calculate start and end points of the scanner segment
            var startX = edge.x1 + (edge.x2 - edge.x1) * scannerStart
            var startY = edge.y1 + (edge.y2 - edge.y1) * scannerStart
            var endX = edge.x1 + (edge.x2 - edge.x1) * scannerEnd
            var endY = edge.y1 + (edge.y2 - edge.y1) * scannerEnd
            
            // Draw glow layer first (thicker, blurred effect)
            ctx.beginPath()
            ctx.moveTo(startX, startY)
            ctx.lineTo(endX, endY)
            
            ctx.strokeStyle = activeCol
            ctx.lineWidth = lineW * 3
            ctx.globalAlpha = 0.3 * glow
            ctx.stroke()
            
            // Draw medium glow
            ctx.beginPath()
            ctx.moveTo(startX, startY)
            ctx.lineTo(endX, endY)
            
            ctx.lineWidth = lineW * 2
            ctx.globalAlpha = 0.5 * glow
            ctx.stroke()
            
            // Draw the bright active segment
            ctx.beginPath()
            ctx.moveTo(startX, startY)
            ctx.lineTo(endX, endY)
            
            ctx.strokeStyle = activeCol
            ctx.lineWidth = lineW
            ctx.globalAlpha = 1.0
            ctx.stroke()
            
            // Draw a bright dot at the leading edge
            ctx.beginPath()
            ctx.arc(endX, endY, lineW * 1.5, 0, Math.PI * 2)
            ctx.fillStyle = activeCol
            ctx.globalAlpha = glow
            ctx.fill()
            
            // Outer glow for the dot
            ctx.beginPath()
            ctx.arc(endX, endY, lineW * 3, 0, Math.PI * 2)
            ctx.fillStyle = activeCol
            ctx.globalAlpha = 0.2 * glow
            ctx.fill()
            
            // Also draw a trail behind showing the already-scanned portion
            // This creates a "filled in" effect for completed edges
            ctx.globalAlpha = 0.6
            ctx.strokeStyle = activeCol
            ctx.lineWidth = lineW
            
            // Draw completed edges
            for (var i = 0; i < currentEdge; i++) {
                var e = edges[i]
                ctx.beginPath()
                ctx.moveTo(e.x1, e.y1)
                ctx.lineTo(e.x2, e.y2)
                ctx.stroke()
            }
            
            // Draw the portion of current edge that's been scanned
            if (scannerStart > 0) {
                ctx.beginPath()
                ctx.moveTo(edge.x1, edge.y1)
                ctx.lineTo(startX, startY)
                ctx.stroke()
            }
        }
    }
    
    // Inner exclamation mark (warning symbol)
    Item {
        id: exclamationMark
        anchors.centerIn: parent
        anchors.verticalCenterOffset: height * 0.08
        width: parent.width * 0.15
        height: parent.height * 0.4
        opacity: root.live ? 1.0 : 0.4
        
        Behavior on opacity {
            NumberAnimation { duration: 300 }
        }
        
        // Exclamation line
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            width: parent.width * 0.5
            height: parent.height * 0.65
            radius: width / 2
            color: root.live ? "#EF4444" : (ThemeManager.isDark() ? "#6B7280" : "#9CA3AF")
            
            Behavior on color {
                ColorAnimation { duration: 300 }
            }
        }
        
        // Exclamation dot
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            width: parent.width * 0.6
            height: width
            radius: width / 2
            color: root.live ? "#EF4444" : (ThemeManager.isDark() ? "#6B7280" : "#9CA3AF")
            
            Behavior on color {
                ColorAnimation { duration: 300 }
            }
        }
    }
}
