import QtQuick 2.15
import QtQuick.Controls 2.15
import "../theme"

Rectangle {
    id: root
    radius: 12
    color: Theme.panel
    border.color: Theme.border
    border.width: 1
    layer.enabled: true
    layer.smooth: true
    
    // Consistent padding - all cards have 16px margins
    implicitWidth: content.childrenRect.width + 32
    implicitHeight: content.childrenRect.height + 32

    // Smooth transitions
    Behavior on color {
        ColorAnimation { duration: 200; easing.type: Easing.InOutQuad }
    }
    Behavior on border.color {
        ColorAnimation { duration: 200; easing.type: Easing.InOutQuad }
    }

    // Content container with consistent 16px padding
    default property alias data: content.data

    Item {
        id: content
        anchors.fill: parent
        anchors.margins: 16
    }

    // Hover/press states
    property bool hovered: false
    property bool pressed: false

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        onEntered: root.hovered = true
        onExited: root.hovered = false
        onPressed: root.pressed = true
        onReleased: root.pressed = false
    }

    // Smooth hover animations
    Behavior on scale { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }
    Behavior on opacity { NumberAnimation { duration: 150 } }

    scale: pressed ? 0.98 : (hovered ? 1.02 : 1.0)
    opacity: enabled ? 1.0 : 0.6
    
    // Subtle glow on hover
    Rectangle {
        anchors.fill: parent
        anchors.margins: -2
        radius: parent.radius
        color: "transparent"
        border.color: Theme.primary
        border.width: 2
        opacity: hovered ? 0.3 : 0
        
        Behavior on opacity {
            NumberAnimation { duration: 150 }
        }
    }
}