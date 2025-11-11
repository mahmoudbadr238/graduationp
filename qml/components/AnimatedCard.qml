import QtQuick 2.15
import QtQuick.Controls 2.15
import "../theme"

Rectangle {
    id: root
    radius: Theme.radii.lg
    color: Theme.glass.card
    border.color: Theme.glass.border
    border.width: 1
    layer.enabled: true
    layer.smooth: true
    
    // NO hardcoded dimensions - let content define size or use Layout
    implicitWidth: content.childrenRect.width + Theme.spacing.xl * 2
    implicitHeight: content.childrenRect.height + Theme.spacing.xl * 2

    // Smooth color transitions
    Behavior on color {
        ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
    }
    Behavior on border.color {
        ColorAnimation { duration: Theme.duration.fast; easing.type: Easing.InOutQuad }
    }

    // Content container
    default property alias data: content.data

    Item {
        id: content
        anchors.fill: parent
        anchors.margins: Theme.spacing.xl
    }

    // Hover/press animation
    property bool hovered: false
    property bool pressed: false

    Behavior on scale { NumberAnimation { duration: Theme.duration.fast; easing.type: Easing.OutCubic } }
    Behavior on opacity { NumberAnimation { duration: Theme.duration.fast } }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        onEntered: root.hovered = true
        onExited: root.hovered = false
        onPressed: root.pressed = true
        onReleased: root.pressed = false
    }

    // Subtle scale on hover, avoid y offset to prevent layout shift
    scale: pressed ? 0.995 : (hovered ? 1.005 : 1.0)
    opacity: enabled ? 1.0 : 0.6
    
    // Neon glow on hover
    Rectangle {
        anchors.fill: parent
        anchors.margins: -2
        radius: parent.radius
        color: "transparent"
        border.color: Theme.neon.purpleGlow
        border.width: 2
        opacity: hovered ? 0.4 : 0
        Behavior on opacity {
            NumberAnimation { duration: Theme.duration.fast }
        }
    }
}