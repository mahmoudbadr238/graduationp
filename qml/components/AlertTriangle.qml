import QtQuick 2.15
import "../theme"

Item {
    id: alert
    property string type: "warn" // warn|danger
    width: 32
    height: 32
    
    Accessible.role: Accessible.Alert
    Accessible.name: type === "danger" ? "Danger" : "Warning"
    
    // Simple warning/danger indicator
    Rectangle {
        anchors.centerIn: parent
        width: 24
        height: 24
        radius: 12
        color: type === "danger" ? Theme.danger : Theme.warning
        
        Text {
            anchors.centerIn: parent
            text: "!"
            color: "white"
            font.pixelSize: 18
            font.weight: Font.Bold
        }
    }
    
    SequentialAnimation on opacity {
        running: type === "warn"
        loops: Animation.Infinite
        NumberAnimation { from: 1.0; to: 0.5; duration: 800 }
        NumberAnimation { from: 0.5; to: 1.0; duration: 800 }
    }
    
    SequentialAnimation on x {
        running: type === "danger"
        loops: 2
        NumberAnimation { from: 0; to: 4; duration: 60 }
        NumberAnimation { from: 4; to: -4; duration: 60 }
        NumberAnimation { from: -4; to: 0; duration: 60 }
    }
}
