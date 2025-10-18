import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: root
    radius: 16
    color: Theme.panel
    border.color: Theme.border
    border.width: 1
    layer.enabled: true
    layer.smooth: true
    implicitWidth: 560
    implicitHeight: 120
    
    // Smooth color transitions
    Behavior on color {
        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
    }
    Behavior on border.color {
        ColorAnimation { duration: 300; easing.type: Easing.InOutQuad }
    }
    
    // Padding
    default property alias data: content.data
    
    Item {
        id: content
        anchors.fill: parent
        anchors.margins: 20
    }
    
    // Hover/press animation (no vertical offset to avoid layout jump)
    property bool hovered: false
    property bool pressed: false
    
    Behavior on y { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
    Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
    Behavior on opacity { NumberAnimation { duration: 120 } }
    
    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        onEntered: root.hovered = true
        onExited: root.hovered = false
        onPressed: root.pressed = true
        onReleased: root.pressed = false
    }
    
    y: 0
    // Keep hover effect subtle to minimize visual overlap
    scale: pressed ? 0.995 : (hovered ? 1.005 : 1.0)
    opacity: enabled ? 1.0 : 0.6
}
