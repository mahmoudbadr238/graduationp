import QtQuick 2.15
import "../ui"

Rectangle {
    id: toast
    
    property string message: ""
    property string toastType: "info"  // "success", "warning", "danger", "info"
    property int duration: 3000
    property real targetY: 0
    
    signal closing()
    
    width: Math.min(400, parent.width - 40)
    height: 56
    radius: 8
    
    color: {
        switch(toastType) {
            case "success": return ThemeManager.success
            case "warning": return ThemeManager.warning
            case "danger": return ThemeManager.danger
            default: return ThemeManager.accent
        }
    }
    
    opacity: 0
    scale: 0.8
    
    // Shadow (removed Qt 6 incompatible ShaderEffect)
    Rectangle {
        anchors.fill: parent
        anchors.margins: -8
        radius: parent.radius + 4
        color: Theme.bg
        opacity: 0.3
        z: -1
        
        Behavior on color {
            ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
        }
    }
    
    Row {
        anchors.centerIn: parent
        spacing: 12
        
        Text {
            text: {
                switch(toastType) {
                    case "success": return "✓"
                    case "warning": return "⚠"
                    case "danger": return "✕"
                    default: return "ℹ"
                }
            }
            font.pixelSize: 20
            font.bold: true
            color: "white"
            anchors.verticalCenter: parent.verticalCenter
        }
        
        Text {
            text: toast.message
            font.pixelSize: 14
            color: "white"
            anchors.verticalCenter: parent.verticalCenter
            elide: Text.ElideRight
            width: Math.min(implicitWidth, toast.width - 80)
        }
    }
    
    // Entry animation
    Component.onCompleted: {
        opacity = 1
        scale = 1
        autoCloseTimer.start()
    }
    
    Behavior on opacity {
        NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
    }
    
    Behavior on scale {
        NumberAnimation { duration: 200; easing.type: Easing.OutBack }
    }
    
    Behavior on y {
        NumberAnimation { duration: 300; easing.type: Easing.OutCubic }
    }
    
    Timer {
        id: autoCloseTimer
        interval: toast.duration
        onTriggered: toast.close()
    }
    
    function close() {
        opacity = 0
        scale = 0.8
        closeTimer.start()
    }
    
    Timer {
        id: closeTimer
        interval: 200
        onTriggered: toast.closing()
    }
    
    MouseArea {
        anchors.fill: parent
        onClicked: toast.close()
        cursorShape: Qt.PointingHandCursor
    }
}
