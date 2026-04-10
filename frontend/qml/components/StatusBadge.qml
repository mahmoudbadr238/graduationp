import QtQuick
import QtQuick.Controls
import "../theme"

Rectangle {
    id: badge
    
    property string text: ""
    property string status: "default" // "success", "warning", "error", "info", "default"
    property bool small: false
    
    implicitWidth: badgeText.implicitWidth + (small ? 16 : 20)
    implicitHeight: small ? 24 : 28
    radius: Theme.radii.pill
    
    color: {
        switch(status) {
            case "success": return Theme.isDark ? "#1a2f2a" : "#e8f5e9"
            case "warning": return Theme.isDark ? "#2f2a1a" : "#fff3e0"
            case "error": return Theme.isDark ? "#2f1a1a" : "#ffebee"
            case "info": return Theme.isDark ? "#1a2a2f" : "#e3f2fd"
            default: return Theme.surface
        }
    }
    
    border.width: 1
    border.color: {
        switch(status) {
            case "success": return Theme.success
            case "warning": return Theme.warning
            case "error": return Theme.error
            case "info": return Theme.info
            default: return Theme.border
        }
    }
    
    Behavior on color {
        ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
    }
    
    Behavior on border.color {
        ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
    }
    
    Text {
        id: badgeText
        anchors.centerIn: parent
        text: badge.text
        color: {
            switch(badge.status) {
                case "success": return Theme.success
                case "warning": return Theme.warning
                case "error": return Theme.error
                case "info": return Theme.info
                default: return Theme.text
            }
        }
        font.pixelSize: badge.small ? 11 : 13
        font.weight: Font.Medium
        
        Behavior on color {
            ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
        }
    }
}
