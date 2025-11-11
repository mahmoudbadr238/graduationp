import QtQuick 2.15
import "../theme"

Item {
    id: root
    property var points: []
    property int maxPoints: 120
    property real strokeWidth: 2
    property color stroke: "#a66bff"
    property color fill: Theme.surface
    implicitWidth: 520
    implicitHeight: 160
    
    Canvas {
        id: canvas
        anchors.fill: parent
        antialiasing: true
        
        onPaint: {
            var ctx = getContext("2d");
            ctx.clearRect(0, 0, width, height);
            
            var n = Math.min(points.length, root.maxPoints);
            if (n < 2) return;
            
            // Fill
            ctx.fillStyle = fill;
            ctx.beginPath();
            for (var i = 0; i < n; i++) {
                var x = (i / (n - 1)) * width;
                var y = height - (points[points.length - n + i] * height);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.lineTo(width, height);
            ctx.lineTo(0, height);
            ctx.closePath();
            ctx.fill();
            
            // Stroke
            ctx.strokeStyle = stroke;
            ctx.lineWidth = strokeWidth;
            ctx.beginPath();
            for (var j = 0; j < n; j++) {
                var xx = (j / (n - 1)) * width;
                var yy = height - (points[points.length - n + j] * height);
                if (j === 0) ctx.moveTo(xx, yy);
                else ctx.lineTo(xx, yy);
            }
            ctx.stroke();
        }
    }
    
    function pushValue(v) {
        points.push(Math.max(0, Math.min(1, v)));
        if (points.length > maxPoints) points.shift();
        canvas.requestPaint();
    }
}
