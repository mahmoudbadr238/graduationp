import QtQuick
import "../ui"

Rectangle {
    id: badge
    
    property real value: 0  // 0-100
    property string label: "Status"
    
    width: 80
    height: 24
    radius: 12
    
    color: {
        if (value < 50) return "#10B981"  // Green - Healthy
        if (value < 75) return "#F59E0B"  // Orange - Warning
        return "#EF4444"                  // Red - Critical
    }
    
    Text {
        anchors.centerIn: parent
        text: {
            if (badge.value < 50) return "Healthy"
            if (badge.value < 75) return "Warning"
            return "Critical"
        }
        color: "#FFFFFF"
        font.pixelSize: 10
        font.bold: true
    }
}
