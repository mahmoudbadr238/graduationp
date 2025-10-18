import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: tile
    radius: 14
    color: Theme.panel
    border.color: Theme.border
    border.width: 1
    implicitWidth: 220
    implicitHeight: 110
    
    // Smooth color transitions
    Behavior on color {
        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
    }
    Behavior on border.color {
        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
    }
    
    property string label: "Metric"
    property string valueText: "--"
    property string hint: ""
    property bool positive: true
    
    Column {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 4
        
        Text {
            text: label
            color: Theme.muted
            font.pixelSize: 13
            
            Behavior on color {
                ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
            }
        }
        
        Text {
            text: valueText
            color: positive ? Theme.success : "#a66bff"
            font.pixelSize: 28
            font.bold: true
            
            Behavior on color {
                ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
            }
        }
        
        Text {
            text: hint
            color: Theme.muted
            font.pixelSize: 12
            
            Behavior on color {
                ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
            }
        }
    }
    
    // Subtle pulse animation (disabled during theme transition)
    SequentialAnimation on border.color {
        loops: Animation.Infinite
        running: !tile.color.r // Pause during color transitions
        ColorAnimation { 
            from: Theme.border
            to: Theme.isDark ? "#3a4160" : "#9ca3af"
            duration: 900 
        }
        ColorAnimation { 
            from: Theme.isDark ? "#3a4160" : "#9ca3af"
            to: Theme.border
            duration: 900 
        }
    }
}
